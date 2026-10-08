"""Literal search using ripgrep, with bounded excerpts and explicit omissions.

No network, persistent cache, or source edits. Explicit masking is opt-in. POSIX only.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import stat
import subprocess
import sys
import time
import unicodedata

from ops_whisper import masking


MAX_EVENT_BYTES = 1024 * 1024
MAX_ARGUMENT_BYTES = 4096


class SearchError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's original message can echo arbitrary argument contents.
        raise SearchError("invalid_arguments", "Invalid arguments; use --help.")


def visible(text: str) -> str:
    """Render controls, including bidi controls, without executing them."""
    parts = []
    for char in text:
        if unicodedata.category(char) in {"Cc", "Cf", "Cs"}:
            code = ord(char)
            parts.append(f"\\u{code:04x}" if code <= 0xFFFF else f"\\U{code:08x}")
        else:
            parts.append(char)
    return "".join(parts)


def utf8_size(value: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeError as error:
        raise SearchError("invalid_input", "Arguments must be valid UTF-8.") from error


def visible_path(value: str) -> str:
    # Keep a literal backslash-u filename distinct from an escaped control.
    return visible(value.replace("\\", "\\\\"))


@dataclass(frozen=True)
class Options:
    query: str
    root: Path
    globs: tuple[str, ...] = ()
    context: int = 2
    max_results: int = 20
    max_chars: int = 8000
    line_chars: int = 400
    timeout: float = 30.0
    json_output: bool = False
    mask_rules: Path | None = None


def validate(options: Options) -> Path:
    if not options.query or any(c in options.query for c in "\x00\r\n"):
        raise SearchError("invalid_input", "Query must be one nonempty literal line.")
    if utf8_size(options.query) > MAX_ARGUMENT_BYTES:
        raise SearchError("invalid_input", "Query exceeds the argument limit.")
    if len(options.globs) > 16 or any(
        not item or "\x00" in item or utf8_size(item) > 512 for item in options.globs
    ):
        raise SearchError("invalid_input", "Invalid or excessive path filters.")
    if not (0 <= options.context <= 10 and 1 <= options.max_results <= 200
            and 512 <= options.max_chars <= 64000 and 32 <= options.line_chars <= 2000
            and math.isfinite(options.timeout) and 0 < options.timeout <= 300):
        raise SearchError("invalid_limits", "Search limits are outside supported ranges.")
    try:
        mode = options.root.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise SearchError("invalid_root", "Root must be a regular file or directory, not a link.")
        root = options.root.resolve(strict=True)
        utf8_size(str(root))
        return root
    except (OSError, ValueError) as error:
        raise SearchError("invalid_root", "Cannot access the supplied root.") from error


def object_text(value: object) -> str:
    if not isinstance(value, dict) or set(value) != {"text"} or not isinstance(value["text"], str):
        raise SearchError("unsupported_text", "Search reported unsupported text or path encoding.", 3)
    text = value["text"]
    try:
        text.encode("utf-8")
    except UnicodeError as error:
        raise SearchError("unsupported_text", "Search reported invalid UTF-8.", 3) from error
    return text


def nonnegative(value: object) -> int:
    if type(value) is not int or value < 0:
        raise SearchError("invalid_backend_output", "Invalid search statistics.", 3)
    return value


def events(command: list[str], cwd: Path, timeout: float):
    """Drain both pipes, cap each JSON record, and reap on all exit paths."""
    try:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    except OSError as error:
        raise SearchError("backend_unavailable", "Cannot start ripgrep.", 3) from error
    deadline = time.monotonic() + timeout
    buffer = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SearchError("timeout", "Search timed out; no excerpts returned.", 3)
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fd, 16384)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "stderr":
                        # Drain without retaining or echoing potentially sensitive diagnostics.
                        continue
                    buffer.extend(chunk)
                    while True:
                        index = buffer.find(b"\n")
                        if index < 0:
                            break
                        if index > MAX_EVENT_BYTES:
                            raise SearchError("event_limit", "Search record exceeds the limit; narrow the input.", 3)
                        record = bytes(buffer[:index])
                        del buffer[:index + 1]
                        try:
                            value = json.loads(record)
                        except (UnicodeError, ValueError, RecursionError) as error:
                            raise SearchError("invalid_backend_output", "Invalid ripgrep JSON output.", 3) from error
                        yield value
                    if len(buffer) > MAX_EVENT_BYTES:
                        raise SearchError("event_limit", "Search record exceeds the limit; narrow the input.", 3)
            if buffer:
                raise SearchError("invalid_backend_output", "Incomplete ripgrep JSON output.", 3)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SearchError("timeout", "Search timed out; no excerpts returned.", 3)
            try:
                code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as error:
                raise SearchError("timeout", "Search timed out; no excerpts returned.", 3) from error
            if code not in (0, 1):
                raise SearchError("backend_failure", "Ripgrep failed; no excerpts returned.", 3)
            yield {"type": "exit", "data": {"code": code}}
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def row(data: dict, line_chars: int, is_match: bool, mask: masking.FileMask | None = None) -> dict:
    original = object_text(data.get("lines"))
    text = original
    if text.endswith("\n"):
        text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
    if "\n" in text or "\r" in text:
        raise SearchError("unsupported_text", "Multiline search records are not supported.", 3)
    line = nonnegative(data.get("line_number"))
    if line == 0:
        raise SearchError("invalid_backend_output", "Invalid source line number.", 3)
    display_text = mask.line(line, original) if mask is not None else original
    if display_text.endswith("\n"):
        display_text = display_text[:-1]
        if display_text.endswith("\r"):
            display_text = display_text[:-1]
    start = 0
    if is_match:
        matches = data.get("submatches")
        if not isinstance(matches, list) or not matches or not isinstance(matches[0], dict):
            raise SearchError("invalid_backend_output", "Missing literal match position.", 3)
        offset = nonnegative(matches[0].get("start"))
        encoded = text.encode("utf-8")
        if offset > len(encoded):
            raise SearchError("invalid_backend_output", "Invalid literal match position.", 3)
        try:
            match_column = len(encoded[:offset].decode("utf-8"))
        except UnicodeError as error:
            raise SearchError("invalid_backend_output", "Invalid UTF-8 match position.", 3) from error
        start = max(0, match_column - min(120, line_chars // 3))
    end = min(len(text), start + line_chars)
    return {"path": visible_path(object_text(data.get("path"))), "line": line,
            "column_start": start + 1, "match": is_match,
            "text": visible(display_text[start:end]), "clipped": start > 0 or end < len(text)}


def search(options: Options) -> dict:
    if os.name != "posix":
        raise SearchError("unsupported_platform", "This development CLI supports macOS and Linux.")
    root = validate(options)
    deadline = time.monotonic() + options.timeout
    policy = masking.load_policy(options.mask_rules, deadline) if options.mask_rules is not None else None
    executable = shutil.which("rg")
    if executable is None:
        raise SearchError("backend_unavailable", "ripgrep (rg) must be installed on PATH.", 3)
    cwd = root if root.is_dir() else root.parent
    target = "." if root.is_dir() else root.name
    command = [executable, "--no-config", "--json", "--fixed-strings", "--case-sensitive",
               "--line-number", "--color", "never", "--encoding", "none", "--sort", "path",
               "--context", str(options.context)]
    for pattern in options.globs:
        command.extend(["--glob", pattern])
    if root.is_dir():
        # Positive rg globs otherwise override the default hidden-file filter.
        # Keep dot files/directories excluded during recursive discovery.
        command.extend(["--glob", "!**/.*"])
    command.extend(["--regexp", options.query, "--", target])
    selected = 0
    matched = 0
    occurrences = 0
    summary = None
    exit_code = None
    before = deque(maxlen=options.context)
    after_until = 0
    kept: dict[tuple[str, int], dict] = {}
    retained_chars = 0
    capture_omitted = False
    active_path = None
    previous_line = 0
    file_mask = None
    mask_bytes = mask_spans = mask_characters = mask_files = 0

    def keep(item: dict) -> None:
        nonlocal retained_chars, capture_omitted
        key = (item["path"], item["line"])
        if key in kept:
            return
        size = len(item["text"]) + len(item["path"]) + 100
        if retained_chars + size > options.max_chars:
            capture_omitted = True
            return
        kept[key] = item
        retained_chars += size

    stream = events(command, cwd, masking.remaining(deadline) if policy is not None else options.timeout)
    try:
        for event in stream:
            if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
                raise SearchError("invalid_backend_output", "Invalid ripgrep event.", 3)
            kind, data = event.get("type"), event["data"]
            if summary is not None and kind != "exit":
                raise SearchError("invalid_backend_output", "Unexpected events after summary.", 3)
            if kind == "begin":
                path = object_text(data.get("path"))
                if active_path is not None or Path(path).is_absolute() or ".." in Path(path).parts:
                    raise SearchError("invalid_backend_output", "Invalid search file boundary.", 3)
                active_path = path
                if policy is not None:
                    file_mask = masking.mask_file(cwd / path, policy, deadline,
                                                  masking.MAX_TOTAL_BYTES - mask_bytes)
                    mask_bytes += file_mask.byte_count
                    mask_spans += file_mask.span_count
                    mask_characters += file_mask.character_count
                    mask_files += 1
                previous_line = 0
                before.clear()
                after_until = 0
            elif kind in {"match", "context"}:
                if active_path is None or object_text(data.get("path")) != active_path:
                    raise SearchError("invalid_backend_output", "Invalid search source boundary.", 3)
                item = row(data, options.line_chars, kind == "match", file_mask)
                if item["line"] <= previous_line:
                    raise SearchError("invalid_backend_output", "Source lines are out of order.", 3)
                previous_line = item["line"]
                if kind == "match":
                    matched += 1
                    occurrences += len(data["submatches"])
                    if selected < options.max_results:
                        selected += 1
                        # Prioritize the match itself over surrounding lines under a budget.
                        keep(item)
                        for prior in before:
                            keep(prior)
                        after_until = item["line"] + options.context
                    elif item["line"] <= after_until:
                        keep(item)
                elif item["line"] <= after_until:
                    keep(item)
                before.append(item)
            elif kind == "end":
                if active_path is None or object_text(data.get("path")) != active_path:
                    raise SearchError("invalid_backend_output", "Invalid search file boundary.", 3)
                if data.get("binary_offset") is not None:
                    raise SearchError("binary_match", "Binary data occurred in a matched file; no excerpts returned.", 3)
                if file_mask is not None:
                    file_mask.verify_source(cwd / active_path, deadline)
                active_path = None
                file_mask = None
                before.clear()
                after_until = 0
            elif kind == "summary":
                if active_path is not None:
                    raise SearchError("invalid_backend_output", "Incomplete file search.", 3)
                summary = data.get("stats")
                if not isinstance(summary, dict):
                    raise SearchError("invalid_backend_output", "Missing search statistics.", 3)
            elif kind == "exit":
                if exit_code is not None or data.get("code") not in (0, 1):
                    raise SearchError("invalid_backend_output", "Invalid backend exit status.", 3)
                exit_code = data["code"]
            else:
                raise SearchError("invalid_backend_output", "Unsupported ripgrep event.", 3)
    finally:
        stream.close()
    if summary is None or exit_code is None:
        raise SearchError("invalid_backend_output", "Search did not finish with statistics.", 3)
    if nonnegative(summary.get("matched_lines")) != matched or nonnegative(summary.get("matches")) != occurrences:
        raise SearchError("invalid_backend_output", "Search counts did not reconcile.", 3)
    if (exit_code == 0) != (matched > 0):
        raise SearchError("invalid_backend_output", "Search exit status did not reconcile.", 3)
    snippets = sorted(kept.values(), key=lambda item: (item["path"], item["line"]))
    return {"schema_version": 1,
            "scope": {"root": visible_path(str(root)),
                      "query": "[WITHHELD]" if policy is not None else visible(options.query),
                      "globs": ["[WITHHELD]" if policy is not None else visible(g) for g in options.globs],
                      "mode": "literal_case_sensitive",
                      "context": options.context, "line_chars": options.line_chars,
                      "max_results": options.max_results, "max_chars": options.max_chars,
                      "timeout_seconds": options.timeout,
                      "recursive_hidden": False, "ignore_policy": "rg_with_explicit_globs"},
            "stats": {"matched_lines": matched, "occurrences": occurrences,
                      "files_searched": nonnegative(summary.get("searches")),
                      "files_with_matches": nonnegative(summary.get("searches_with_match")),
                      "bytes_searched": nonnegative(summary.get("bytes_searched"))},
            "display": {"selected_match_lines": selected,
                        "returned_match_lines": sum(item["match"] for item in snippets),
                        "omitted_match_lines": matched - sum(item["match"] for item in snippets),
                        "clipped_lines": sum(item["clipped"] for item in snippets),
                        "truncated": selected < matched or capture_omitted or any(item["clipped"] for item in snippets)},
            "scan_completed": True, "redacted": policy is not None,
            "masking": {"applied": policy is not None, "builtin_version": masking.BUILTIN_VERSION,
                        "scope": "matched_file_text", "rule_count": policy.active_count if policy else 0,
                        "files_checked": mask_files, "bytes_checked": mask_bytes,
                        "spans": mask_spans, "characters": mask_characters},
            "lines": snippets}


def encode(result: dict, as_json: bool) -> str:
    if as_json:
        return json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    scope, stats, display = result["scope"], result["stats"], result["display"]
    out = [f'root={scope["root"]}', f'query={scope["query"]} mode={scope["mode"]}',
           f'globs={json.dumps(scope["globs"], ensure_ascii=False)} context={scope["context"]} line_chars={scope["line_chars"]}',
           f'max_results={scope["max_results"]} max_chars={scope["max_chars"]} timeout_seconds={scope["timeout_seconds"]}',
           f'matched_lines={stats["matched_lines"]} occurrences={stats["occurrences"]} files_searched={stats["files_searched"]} files_with_matches={stats["files_with_matches"]} bytes_searched={stats["bytes_searched"]}',
           f'returned_match_lines={display["returned_match_lines"]} omitted_match_lines={display["omitted_match_lines"]} clipped_lines={display["clipped_lines"]} truncated={str(display["truncated"]).lower()}',
           f'scan_completed=true scope=rg_filtered_files redacted={str(result["redacted"]).lower()}']
    if result["masking"]["applied"]:
        mask = result["masking"]
        out.append(f'masking_scope=matched_file_text rules={mask["rule_count"]} files_checked={mask["files_checked"]} masked_spans={mask["spans"]} masked_characters={mask["characters"]} paths_masked=false')
    for item in result["lines"]:
        flag = ">" if item["match"] else " "
        cut = " [clipped]" if item["clipped"] else ""
        out.append(f'{flag} {item["path"]}:{item["line"]}:{item["column_start"]}{cut} {item["text"]}')
    return "\n".join(out) + "\n"


def render(result: dict, as_json: bool, max_chars: int) -> str:
    """Bound the entire serialized response, including metadata and escapes."""
    while True:
        text = encode(result, as_json)
        if len(text) <= max_chars:
            return text
        if not result["lines"]:
            raise SearchError("output_limit", "Metadata exceeds the output budget; shorten the scope or increase --max-chars.")
        # Remove context first. Then omit complete match records, never broken JSON.
        index = next((i for i in range(len(result["lines"]) - 1, -1, -1)
                      if not result["lines"][i]["match"]), len(result["lines"]) - 1)
        removed = result["lines"].pop(index)
        display = result["display"]
        display["truncated"] = True
        if removed["match"]:
            display["returned_match_lines"] -= 1
            display["omitted_match_lines"] += 1
        if removed["clipped"]:
            display["clipped_lines"] -= 1


def parser() -> Parser:
    cli = Parser(prog="ops-whisper", description="Bounded local search. Masking requires explicit --mask-rules.")
    cli.add_argument("--version", action="version", version="ops-whisper development")
    commands = cli.add_subparsers(dest="command", required=True, parser_class=Parser)
    cmd = commands.add_parser("search", help="Search a literal string using rg.")
    cmd.add_argument("query", help="Nonempty, case-sensitive literal text; use -- before a leading dash.")
    cmd.add_argument("--root", type=Path, required=True, help="Explicit regular file or directory.")
    cmd.add_argument("--glob", action="append", default=[], help="rg path filter; repeat to combine filters.")
    cmd.add_argument("--context", type=int, default=2, help="Adjacent lines (0..10; default: 2).")
    cmd.add_argument("--max-results", type=int, default=20, help="Primary matching lines (1..200; default: 20).")
    cmd.add_argument("--max-chars", type=int, default=8000, help="Whole response character budget (512..64000).")
    cmd.add_argument("--line-chars", type=int, default=400, help="Source characters per line excerpt (32..2000).")
    cmd.add_argument("--timeout", type=float, default=30.0, help="Search deadline in seconds (0..300, excluding 0).")
    cmd.add_argument("--json", action="store_true", help="Return one compact JSON object.")
    cmd.add_argument("--mask-rules", type=Path, help="Explicit masking TOML; apply rules before excerpting.")
    return cli


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        options = Options(query=args.query, root=args.root, globs=tuple(args.glob),
                          context=args.context, max_results=args.max_results, max_chars=args.max_chars,
                          line_chars=args.line_chars, timeout=args.timeout, json_output=args.json,
                          mask_rules=args.mask_rules)
        result = search(options)
        text = render(result, options.json_output, options.max_chars)
        sys.stdout.write(text)
        sys.stdout.flush()
        return 0 if result["stats"]["matched_lines"] else 1
    except SearchError as error:
        print(f"ops-whisper: {error.code}: {error}", file=sys.stderr)
        return error.exit_code
    except masking.MaskError as error:
        print(f"ops-whisper: {error.code}: {error}", file=sys.stderr)
        return error.exit_code
    except KeyboardInterrupt:
        print("ops-whisper: interrupted; no completed result.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # Prevent a second buffered flush from producing an interpreter diagnostic.
        try:
            descriptor = sys.stdout.fileno()
            with open(os.devnull, "w") as sink:
                os.dup2(sink.fileno(), descriptor)
        except (OSError, ValueError):
            pass
        return 141
    except (OSError, UnicodeError):
        print("ops-whisper: io_error: Cannot read or write search data.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
