"""Explicit TOML masking policies and a deadline-bounded regex worker.

The worker receives source text through stdin and returns only character spans.
No files, persistent caches, network calls, or original-value diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import tomllib
import warnings


MAX_CONFIG_BYTES = 65536
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_RULES = 32
MAX_PATTERN_BYTES = 1024
MAX_SPANS = 10000
WORKER_SECONDS = 2.0
BUILTIN_VERSION = 1
FLAGS = {"IGNORECASE": re.IGNORECASE, "MULTILINE": re.MULTILINE, "DOTALL": re.DOTALL}
BUILTINS = {
    "bearer": r'''(?i)\bBearer[ \t]+[^\s"'<>]+''',
    "credential_assignment": (
        r'''(?im)(?<![\w-])(?:password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret|token|secret)'''
        r'''["']?[ \t]*[:=][ \t]*(?:"(?:\\[\s\S]|[^"\\]|\\\Z)*(?:"|\Z)|'''
        r"'(?:\\[\s\S]|[^'\\]|\\\Z)*(?:'|\Z)|[^\s,;\"'<>]+)"
    ),
    "private_key": (
        r"-----BEGIN ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----"
        r"[\s\S]*?(?:-----END \1-----|\Z)"
    ),
}


class MaskError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 3):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    flags: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True)
class Policy:
    rules: tuple[Rule, ...]

    @property
    def active_count(self) -> int:
        return sum(rule.enabled for rule in self.rules)


def remaining(deadline: float) -> float:
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise MaskError("mask_timeout", "Masking deadline exceeded; no result returned.")
    return seconds


def fingerprint(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read_regular(path: Path, limit: int, deadline: float) -> tuple[bytes, tuple[int, int, int, int, int]]:
    """Bound input; reject final links/nonregular files and observable changes."""
    remaining(deadline)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise MaskError("mask_input", "Masking requires a regular file.")
            if before.st_size > limit:
                raise MaskError("mask_input_limit", "Masking input exceeds its byte limit.")
            data = source.read(limit + 1)
            after = os.fstat(source.fileno())
    except (OSError, ValueError) as error:
        raise MaskError("mask_input", "Cannot read masking input.") from error
    remaining(deadline)
    if len(data) > limit:
        raise MaskError("mask_input_limit", "Masking input exceeds its byte limit.")
    if fingerprint(before) != fingerprint(after) or len(data) != after.st_size:
        raise MaskError("mask_input_changed", "Masking input changed; no result returned.")
    return data, fingerprint(after)


def load_policy(path: Path, deadline: float) -> Policy:
    try:
        raw, _ = read_regular(path, MAX_CONFIG_BYTES, deadline)
        config = tomllib.loads(raw.decode("utf-8"))
        if set(config) - {"schema_version", "builtins", "rules"}:
            raise ValueError
        if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
            raise ValueError
        names = config.get("builtins", list(BUILTINS))
        if not isinstance(names, list) or any(not isinstance(n, str) or n not in BUILTINS for n in names):
            raise ValueError
        if len(names) != len(set(names)):
            raise ValueError
        rules = [Rule(name, BUILTINS[name]) for name in names]
        custom = config.get("rules", [])
        if not isinstance(custom, list) or len(custom) + len(rules) > MAX_RULES:
            raise ValueError
        for item in custom:
            if not isinstance(item, dict) or set(item) - {"id", "pattern", "action", "enabled", "flags"}:
                raise ValueError
            name, pattern = item.get("id"), item.get("pattern")
            if not isinstance(name, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None:
                raise ValueError
            if not isinstance(pattern, str) or not pattern or len(pattern.encode("utf-8")) > MAX_PATTERN_BYTES:
                raise ValueError
            if "\x00" in pattern or item.get("action") != "mask":
                raise ValueError
            flags = item.get("flags", [])
            enabled = item.get("enabled", True)
            if type(enabled) is not bool or not isinstance(flags, list):
                raise ValueError
            if any(not isinstance(f, str) or f not in FLAGS for f in flags) or len(flags) != len(set(flags)):
                raise ValueError
            rules.append(Rule(name, pattern, tuple(flags), enabled))
        if len({r.id for r in rules}) != len(rules) or not any(r.enabled for r in rules):
            raise ValueError
        policy = Policy(tuple(rules))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise MaskError("invalid_mask_rules", "Invalid masking TOML or rule schema.", 2) from error
    # Compile and test empty-string matches even when search will have zero hits.
    run_worker(policy, "", deadline)
    return policy


def run_worker(policy: Policy, text: str, deadline: float) -> list[tuple[int, int]]:
    payload = json.dumps({"rules": [asdict(r) for r in policy.rules], "text": text}, ensure_ascii=True).encode()
    remaining(deadline)
    try:
        process = subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--worker"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError as error:
        raise MaskError("mask_worker", "Cannot start masking worker.") from error
    try:
        try:
            output, _ = process.communicate(payload, timeout=min(WORKER_SECONDS, remaining(deadline)))
        except subprocess.TimeoutExpired as error:
            raise MaskError("mask_timeout", "Masking timed out; no result returned.") from error
        remaining(deadline)
        if process.returncode != 0 or len(output) > 1024 * 1024:
            raise MaskError("mask_worker", "Masking worker failed; no result returned.")
        try:
            value = json.loads(output)
            if isinstance(value, dict) and value.get("error") == "invalid_pattern":
                raise MaskError("invalid_mask_pattern", "Invalid or empty matching regex.", 2)
            if isinstance(value, dict) and value.get("error") == "span_limit":
                raise MaskError("mask_span_limit", "Masking match limit exceeded; no result returned.")
            if not isinstance(value, dict) or set(value) != {"spans"} or not isinstance(value["spans"], list):
                raise ValueError
            spans = value["spans"]
            if len(spans) > MAX_SPANS:
                raise ValueError
            end = -1
            for pair in spans:
                if not isinstance(pair, list) or len(pair) != 2 or any(type(n) is not int for n in pair):
                    raise ValueError
                start, stop = pair
                if not (end < start < stop <= len(text)):
                    raise ValueError
                end = stop
            return [(a, b) for a, b in spans]
        except (ValueError, UnicodeError, RecursionError) as error:
            raise MaskError("mask_worker", "Invalid masking worker result.") from error
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


def detect(rules: list[dict], text: str) -> list[list[int]]:
    """Worker-only regex evaluation; overlaps union without priority conflicts."""
    spans = []
    for rule in rules:
        flags = 0
        for name in rule["flags"]:
            flags |= FLAGS[name]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                pattern = re.compile(rule["pattern"], flags)
            if pattern.search("") is not None:
                raise MaskError("invalid_pattern", "")
            if not rule["enabled"]:
                continue
            for match in pattern.finditer(text):
                if match.start() == match.end():
                    raise MaskError("invalid_pattern", "")
                spans.append((match.start(), match.end()))
                if len(spans) > MAX_SPANS:
                    raise MaskError("span_limit", "")
        except (re.error, Warning, RecursionError, OverflowError) as error:
            raise MaskError("invalid_pattern", "") from error
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


@dataclass
class FileMask:
    raw_lines: list[str]
    masked_lines: list[str]
    byte_count: int
    span_count: int
    character_count: int
    identity: tuple[int, int, int, int, int] | None = None

    def line(self, number: int, raw: str) -> str:
        if not (1 <= number <= len(self.raw_lines)) or self.raw_lines[number - 1] != raw:
            raise MaskError("mask_input_changed", "Search and masking input differ; no result returned.")
        return self.masked_lines[number - 1]

    def verify_source(self, path: Path, deadline: float) -> None:
        remaining(deadline)
        try:
            current = path.stat(follow_symlinks=False)
        except OSError as error:
            raise MaskError("mask_input_changed", "Masking source changed; no result returned.") from error
        if self.identity != fingerprint(current):
            raise MaskError("mask_input_changed", "Masking source changed; no result returned.")


def source_lines(text: str) -> list[str]:
    # rg uses LF boundaries; str.splitlines would also split Unicode separators.
    parts = text.split("\n")
    return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def mask_file(path: Path, policy: Policy, deadline: float, available_bytes: int) -> FileMask:
    data, identity = read_regular(path, min(MAX_FILE_BYTES, available_bytes), deadline)
    try:
        raw = data.decode("utf-8")
    except UnicodeError as error:
        raise MaskError("mask_encoding", "Masking input must be UTF-8.") from error
    if "\x00" in raw:
        raise MaskError("mask_encoding", "Masking input contains binary data.")
    spans = run_worker(policy, raw, deadline)
    pieces = []
    offset = 0
    count = 0
    for start, end in spans:
        pieces.append(raw[offset:start])
        segment = raw[start:end]
        count += len(segment) - segment.count("\r") - segment.count("\n")
        pieces.append(re.sub(r"[^\r\n]", "*", segment))
        offset = end
    pieces.append(raw[offset:])
    masked = "".join(pieces)
    remaining(deadline)
    return FileMask(source_lines(raw), source_lines(masked), len(data), len(spans), count, identity)


def worker_main() -> int:
    try:
        request = json.load(sys.stdin)
        result = {"spans": detect(request["rules"], request["text"])}
    except MaskError as error:
        result = {"error": error.code}
    except Exception:
        # The parent never receives traceback text, source text, or regex values.
        result = {"error": "worker_failure"}
    sys.stdout.write(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit(2)
    raise SystemExit(worker_main())
