#!/usr/bin/env python3
"""Reproduce SR-02 using only the pinned bundled synthetic fixture.

No real input paths, cloud access, source edits, persistent output, or cleanup.
The manifest defines expected evidence independently of CLI results. Exit 0
means expected successes AND known limitations reproduced, not safe to share.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/search-trial"


class TrialFailure(Exception):
    pass


def require(condition: bool, description: str) -> None:
    if not condition:
        raise TrialFailure(description)


def run(command: list[str]) -> str:
    process = None
    try:
        process = subprocess.Popen(command, cwd=FIXTURE, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", start_new_session=True)
        output, errors = process.communicate(timeout=15)
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
        raise TrialFailure("Cannot complete the synthetic command.") from error
    finally:
        if process is not None and process.poll() is None:
            # The trial owns this entire group, including CLI workers and rg.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
    require(process.returncode == 0 and not errors, "Synthetic command failed or produced diagnostics.")
    return output


def sizes(text: str) -> dict:
    return {"characters": len(text), "utf8_bytes": len(text.encode("utf-8"))}


def native_rows(output: str) -> tuple[dict[int, str], list[int], dict]:
    rows, matches, summary = {}, [], None
    for record in output.splitlines():
        event = json.loads(record)
        if event["type"] in {"match", "context"}:
            data = event["data"]
            rows[data["line_number"]] = data["lines"]["text"].removesuffix("\n")
            if event["type"] == "match":
                matches.append(data["line_number"])
        elif event["type"] == "summary":
            summary = event["data"]["stats"]
    require(summary is not None, "Missing native search summary.")
    return rows, matches, summary


def evaluate_case(case: dict, expected: dict, source: Path, source_lines: list[str], rg: str) -> dict:
    base = [rg, "--no-config", "--fixed-strings", "--case-sensitive", "--encoding", "none",
            "--sort", "path", "--context", str(case["context"])]
    suffix = ["--regexp", case["query"], "--", source.name]
    native_json = run(base + ["--json"] + suffix)
    native_text = run(base + ["--line-number", "--with-filename", "--color", "never"] + suffix)
    rows, matches, summary = native_rows(native_json)
    require(len(matches) == case["matched_lines"] == summary["matched_lines"],
            "Native counts differ from the authored expectation.")
    require(all(rows[n] == source_lines[n - 1] for n in rows), "Native source positions differ.")

    command = [sys.executable, str(ROOT / "ops-whisper"), "search", "--root", str(source),
               "--context", str(case["context"]), "--max-results", str(case["max_results"]),
               "--max-chars", str(case["max_chars"]), "--timeout", "5", "--json"]
    plain_output = run(command + ["--", case["query"]])
    masked_output = run(command + ["--mask-rules", str(FIXTURE / case["policy"]), "--", case["query"]])
    plain, masked = json.loads(plain_output), json.loads(masked_output)
    for data, output in ((plain, plain_output), (masked, masked_output)):
        require(data["scan_completed"], "Search was not complete.")
        require(data["stats"]["matched_lines"] == case["matched_lines"], "Wrapper count differs.")
        require(data["stats"]["occurrences"] == summary["matches"], "Occurrence count differs.")
        require([r["line"] for r in data["lines"] if r["match"]] == case["returned_match_lines"],
                "Returned matching lines differ from the authored expectation.")
        require(len(output) <= case["max_chars"], "Whole response exceeded its budget.")
        require(data["display"]["omitted_match_lines"] == case["matched_lines"] - len(case["returned_match_lines"]),
                "Omitted count differs.")
        require(all(r["path"] == source.name and r["column_start"] == 1 and not r["clipped"] for r in data["lines"]),
                "Fixture excerpts lost their source path, column, or complete line.")
    require([r["line"] for r in plain["lines"]] == [r["line"] for r in masked["lines"]],
            "Masking changed the returned source positions in this trial.")
    require(all(r["text"] == rows[r["line"]] for r in plain["lines"]), "Unmasked wrapper differs from native rows.")
    require(not plain["redacted"] and masked["redacted"] and masked["masking"]["files_checked"] == 1,
            "Policy application was not recorded correctly.")
    require(masked["scope"]["query"] == "[WITHHELD]", "Masked query was echoed.")
    require(all(len(a["text"]) == len(b["text"]) for a, b in zip(plain["lines"], masked["lines"])),
            "Masking changed fixture line lengths.")

    body = {r["line"]: r["text"] for r in masked["lines"]}
    evidence = {int(n): fields for n, fields in expected["evidence_fields"].items()}
    present = sorted(set(body) & set(evidence))
    missing = sorted(set(evidence) - set(body))
    useful = not missing and all(all(field in body[n] for field in fields) for n, fields in evidence.items())
    unknown = expected["ground_truth"]["unknown_secret"] in masked_output
    require(present == case["evidence_lines"] and missing == case["missing_evidence_lines"],
            "Evidence presence differs from the authored expectation.")
    require(useful == case["useful_fields_preserved"], "Evidence fields differ from the expected preservation/loss.")
    require(unknown == case["unknown_secret_visible"], "Unknown-secret observation differs.")
    require(not any(marker in masked_output for marker in expected["ground_truth"]["known_secret_markers"]),
            "A known synthetic secret marker remained in the masked response.")
    if "counter_visible" in case:
        counter = expected["ground_truth"]["counter_field"] in body[expected["ground_truth"]["counter_line"]]
        require(counter == case["counter_visible"], "Nonsecret-counter observation differs.")
    if case.get("key_line_fully_masked"):
        n = expected["ground_truth"]["key_middle_line"]
        require(body[n] == "*" * len(source_lines[n - 1]), "Key middle excerpt was not fully masked.")

    return {"id": case["id"], "expectation_reproduced": True, "policy": case["policy"],
            "matched_lines": case["matched_lines"], "occurrences": masked["stats"]["occurrences"],
            "returned_match_lines": len(case["returned_match_lines"]),
            "omitted_match_lines": masked["display"]["omitted_match_lines"],
            "evidence_lines": present, "missing_evidence_lines": missing,
            "useful_fields_preserved": useful, "unknown_secret_visible": unknown,
            "observed_limitation": case["limitation"],
            "output": {"rg_text": sizes(native_text), "ops_json": sizes(plain_output),
                       "masked_ops_json": sizes(masked_output)},
            "masked_spans_in_full_file": masked["masking"]["spans"]}


def evaluate() -> dict:
    expected = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    require(expected["schema_version"] == 1 and expected["source"] == "infra.synthetic.txt",
            "Unsupported synthetic manifest.")
    source = FIXTURE / expected["source"]
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    require(digest == expected["source_sha256"], "Synthetic fixture hash changed; review the manifest before testing.")
    source_lines = original.decode("utf-8").splitlines()
    require(len(source_lines) == expected["source_lines"], "Synthetic source line count differs.")
    for n, fields in expected["evidence_fields"].items():
        require(all(field in source_lines[int(n) - 1] for field in fields), "Authored evidence location differs.")
    a, b = expected["duplicate_lines"]
    require(source_lines[a - 1] == source_lines[b - 1], "Authored duplicate is no longer identical.")
    rg = shutil.which("rg")
    require(rg is not None, "Install rg on PATH to run this synthetic trial.")
    cases = [evaluate_case(case, expected, source, source_lines, rg) for case in expected["cases"]]
    require(hashlib.sha256(source.read_bytes()).hexdigest() == digest, "Trial edited its source fixture.")
    return {"schema_version": 1, "synthetic_only": True, "fixture_sha256": digest,
            "fixture_lines": len(source_lines), "fixture_bytes": len(original),
            "environment": {"python": platform.python_version(), "platform": platform.system(),
                            "architecture": platform.machine(), "rg": run([rg, "--version"]).splitlines()[0]},
            "measurement": "Unicode code points and UTF-8 bytes; no token, speed, or real-work value estimate",
            "implementation_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                      for name in ("ops_whisper/cli.py", "ops_whisper/masking.py")},
            "policy_sha256": {name: hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
                              for name in ("builtins.toml", "focused.toml", "overbroad.toml")},
            "source_unchanged": True, "all_expectations_reproduced": True,
            "safe_to_share_certified": False, "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Return summary JSON, without raw log excerpts.")
    args = parser.parse_args()
    try:
        result = evaluate()
    except KeyboardInterrupt:
        print("Synthetic trial interrupted; no completed comparison.", file=sys.stderr)
        return 130
    except (TrialFailure, OSError, ValueError, KeyError, TypeError) as error:
        # Restrict output to stable diagnostics; do not print subprocess streams.
        description = str(error) if isinstance(error, TrialFailure) else "Invalid synthetic fixture or result."
        print("Synthetic trial failed: " + description, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("SR-02 synthetic trial: authored expectations reproduced (including known limitations).")
        print(f'Fixture: {result["fixture_lines"]} lines, {result["fixture_bytes"]} bytes; source unchanged.')
        print("case | matched/returned/omitted | rg text / ops JSON / masked JSON characters | observation")
        for case in result["cases"]:
            out = case["output"]
            counts = f'{case["matched_lines"]}/{case["returned_match_lines"]}/{case["omitted_match_lines"]}'
            lengths = " / ".join(str(out[name]["characters"]) for name in ("rg_text", "ops_json", "masked_ops_json"))
            print(f'{case["id"]} | {counts} | {lengths} | {case["observed_limitation"] or "specified evidence/mask preserved"}')
        print("This result is not a sharing-safety, token-cost, speed, or real-work value certification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
