#!/usr/bin/env python3
"""Check repository documentation without network access or third-party packages.

Checks file targets, required files, whitespace, basic README parity, and synthetic TOML
structure. Does not check anchors, external links, prose translation, or CLI
behavior. Python 3.11+ is required for the standard-library TOML parser.
"""

from pathlib import Path
import re
import sys
import tomllib
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "README.en.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md",
    "CODE_OF_CONDUCT.md", "CHANGELOG.md", "docs/DESIGN.md",
    "docs/MILESTONES.md", "docs/THREAT_MODEL.md", "docs/OSS_READINESS.md",
    "docs/PRODUCT_REVIEW.md", "docs/TASKS.md", "docs/REVIEW_FLOW.md",
    "docs/evaluation/INFRA_REPORT_TEMPLATE.md",
    "docs/INFRA_REPORT_WORKFLOW.md", "docs/evaluation/INFRA_REPORT_EXAMPLE.md",
    "docs/evaluation/INFRA_REPORT_TRIAL.md",
    "docs/REQUIREMENTS_RECOVERY.md", "docs/evaluation/REQUIREMENTS_RECOVERY_TEMPLATE.md",
    "examples/infra-report.submission.synthetic.md",
    "docs/evaluation/TEMPLATE.md", "docs/license/MIT-LICENSE.txt",
    "examples/input.synthetic.txt", "examples/output.synthetic.txt",
    "examples/rules.synthetic.toml", ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml", ".github/pull_request_template.md",
    ".github/workflows/docs.yml", ".editorconfig", ".gitignore",
    "scripts/check_docs.py",
    "docs/SEARCH_CLI.md", "ops-whisper", "ops_whisper/__init__.py",
    "ops_whisper/cli.py", "tests/test_search.py",
    "docs/MASKING.md", "ops_whisper/masking.py", "tests/test_masking.py",
    "examples/masking.synthetic.toml",
    "scripts/run_search_trial.py", "examples/search-trial/infra.synthetic.txt",
    "examples/search-trial/expected.json", "examples/search-trial/builtins.toml",
    "examples/search-trial/focused.toml", "examples/search-trial/overbroad.toml",
    "docs/evaluation/SEARCH_SYNTHETIC_TRIAL.md",
    "docs/evaluation/search-synthetic-result.json",
    "THIRD_PARTY_NOTICES.md", "docs/evaluation/PF_PACK.md",
    "docs/evaluation/publication-files.txt",
    "docs/evaluation/PF_PUBLISH.md",
)
LINK = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")
FENCE = re.compile(r"^```(.*)$", re.MULTILINE)
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


for name in REQUIRED:
    path = ROOT / name
    require(path.is_file(), f"Missing required file: {name}")
    if not path.is_file():
        continue
    try:
        content = path.read_bytes().decode("utf-8")
        require(content.endswith("\n"), f"Missing final newline: {name}")
        require("\r" not in content, f"Unexpected carriage return: {name}")
        for number, line in enumerate(content.splitlines(), start=1):
            require(line == line.rstrip(" \t"),
                    f"Trailing whitespace: {name}:{number}")
    except (OSError, UnicodeError):
        errors.append(f"Cannot read required UTF-8 file: {name}")

documents = [ROOT / name for name in REQUIRED if name.endswith(".md")]
readmes: list[str] = []
for path in documents:
    if not path.is_file():
        continue
    name = str(path.relative_to(ROOT))
    try:
        body = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        errors.append(f"Cannot read UTF-8 documentation: {name}")
        continue
    require(body.endswith("\n"), f"Missing final newline: {name}")
    require(body.startswith("# "), f"Missing document title: {name}")
    require(len(FENCE.findall(body)) % 2 == 0, f"Unbalanced code fences: {name}")
    for target in LINK.findall(body):
        # The repository uses simple inline links without titles or spaces.
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        resolved = (path.parent / unquote(url.path)).resolve()
        require(resolved.is_relative_to(ROOT), f"Link escapes repository: {name}")
        require(resolved.is_file(), f"Missing local link target in {name}: {target}")
    if path.name in ("README.md", "README.en.md"):
        readmes.append(body)

if len(readmes) == 2:
    for body in readmes:
        require(body.startswith("# ops-whisper\n"), "Unexpected README project name")
    require(readmes[0].count("\n## ") == readmes[1].count("\n## "),
            "README section counts differ")
    blocks = [re.findall(r"```[^\n]*\n(.*?)```", body, re.DOTALL)
              for body in readmes]
    require(len(blocks[0]) == len(blocks[1]), "README code block counts differ")
    if len(blocks[0]) == len(blocks[1]):
        for japanese, english in zip(blocks[0], blocks[1]):
            strip_comments = lambda value: "\n".join(
                line for line in value.splitlines() if not line.startswith("#")
            )
            require(strip_comments(japanese) == strip_comments(english),
                    "README examples or commands differ")

rules_path = ROOT / "examples/rules.synthetic.toml"
if rules_path.is_file():
    try:
        rules = tomllib.loads(rules_path.read_text(encoding="utf-8"))
        require(rules.get("schema_version") == 1, "Unexpected example schema")
        rows = rules.get("rules", [])
        ids = [row.get("id") for row in rows]
        require(len(ids) == len(set(ids)), "Duplicate example rule IDs")
        for row in rows:
            require(row.get("literal") not in (None, ""), "Empty example literal")
            require(row.get("match") in ("exact_token", "substring"),
                    "Unknown example match mode")
            require(row.get("action") in ("mask", "alias"), "Unknown example action")
            if row.get("action") == "alias":
                require(row.get("category") in ("CLIENT", "HOST", "USER", "PATH"),
                        "Unknown example alias category")
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        errors.append("Cannot parse synthetic TOML example")

mask_path = ROOT / "examples/masking.synthetic.toml"
if mask_path.is_file():
    try:
        mask = tomllib.loads(mask_path.read_text(encoding="utf-8"))
        require(mask.get("schema_version") == 1, "Unexpected search masking example schema")
        require(mask.get("builtins") == ["bearer", "credential_assignment", "private_key"],
                "Unexpected search masking example builtins")
        for row in mask.get("rules", []):
            require(row.get("action") == "mask" and bool(row.get("pattern")),
                    "Invalid search masking example rule")
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        errors.append("Cannot parse search masking TOML example")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(1)

print(f"Documentation checks passed: {len(documents)} Markdown files; "
      "local file links, whitespace, README structure/examples, and synthetic TOML.")
