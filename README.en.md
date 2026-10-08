# ops-whisper

[日本語](README.md)

**A small local search CLI that bounds returned output while retaining source positions, match counts, and explicit omissions.**

It searches text with existing ripgrep and returns line-linked excerpts as text or JSON. An explicit TOML policy can mask complete matched files before excerpting. It helps readers return from code or log excerpts to the source and identify matches left out of the display.

## Current status

**The feature scope is closed as a small portfolio CLI.** Search, body masking, and the fixed synthetic comparison have been checked locally. PF-1, a reproducible and explainable portfolio CLI, is the completion target for this development scope. Preparing an OSS publication candidate and publishing it are separate stages. No distribution or global installation is provided.

Checks were run on macOS arm64 with Python 3.14.7 and rg 15.2.0. A Linux rehearsal also passed on Debian 12 arm64 with Python 3.11.2 and rg 13.0.0. GitHub remote CI remains unverified and Windows has not been tested. Real-workflow time savings, token cost reductions, and secret detection accuracy have not been demonstrated.

## Usage

Python 3.11 or later and `rg` on PATH are required. Run from this checkout; no additional Python packages are needed.

```sh
./ops-whisper search 'host=' --root examples/input.synthetic.txt --context 0
./ops-whisper search 'host=' --root examples/input.synthetic.txt --mask-rules examples/masking.synthetic.toml --json
./ops-whisper search 'status=503' --root examples/input.synthetic.txt --context 0 --max-results 5 --max-chars 2000 --json
./ops-whisper search 'SearchError' --root ops_whisper --glob '*.py' --max-results 5
./ops-whisper search --help
```

Queries are case-sensitive literal strings, and `--root` is required. Defaults are two context lines, twenty primary matching lines, and 8000 characters for the whole response. The eligible scope is scanned to obtain totals; the returned output is bounded. Excerpts are neither relevance-ranked nor representative samples. Direct rg may be simpler for basic filtering or returning every match. The [search contract](docs/SEARCH_CLI.md) describes JSON, exit codes, scope, and limits.

Explicit `--mask-rules` applies builtins and custom regex to complete matched files. Text is masked while retaining line endings and character positions, then excerpted. `redacted:true` records policy application, not complete detection or permission to share. Without the option, original text is returned. Roots and filenames are not masked; unknown secrets and excessive masking remain possible. Read the [masking contract](docs/MASKING.md) and review output before sharing.

Recursive discovery excludes hidden files and does not follow links, but positive globs may include ignored regular files. Explicitly selected files and changing inputs are not isolated by a sandbox.

## Try synthetic data

No real logs or business documents are needed. A fabricated infrastructure log and independently authored expectations are included.

```sh
# A broad search leaves later failure and recovery records out of the excerpt.
./ops-whisper search 'service=demo-api' --root examples/search-trial/infra.synthetic.txt --context 0 --max-results 5 --max-chars 3000 --json
# Narrow the question to a request and its attempts to recover the observations.
./ops-whisper search 'request=demo-42 attempt=' --root examples/search-trial/infra.synthetic.txt --context 1 --max-results 10 --max-chars 6000 --mask-rules examples/search-trial/focused.toml --json
# Check six cases including retained/lost evidence, unknown secrets, and overmasking.
python3 scripts/run_search_trial.py
```

The broad search returns five of 313 matching lines and omits the required failure, retry, and recovery records. The narrow query returns four evidence observations. These include a repeated collection of one event, so there are three distinct attempts. Search match counts are not incident counts.

A successful comparison means known failure cases were also reproduced as expected. It does not certify sharing safety. In the narrow comparison, rg text used 1383 characters and masked JSON used 2894, so JSON is not always smaller. The [synthetic comparison report](docs/evaluation/SEARCH_SYNTHETIC_TRIAL.md) records conditions and limits.

## Completion goals and design

| Stage | What reaching it delivers | Status |
| --- | --- | --- |
| PF-0 | A working small CLI | Locally complete |
| PF-1 | A reproducible and explainable portfolio CLI | Locally complete; end of this feature development scope |
| PF-2 | An OSS publication candidate others can try | Locally complete; MIT adopted |
| PF-3 | A source-published portfolio OSS project | Publication approved; CI rehearsal passed; notification settings and remote CI remain pending |

[Milestones](docs/MILESTONES.md) define completion and stopping points, [tasks](docs/TASKS.md) record remaining work, and [OSS readiness](docs/OSS_READINESS.md) covers publication conditions. Design evidence includes search scope and output budgets, full-file masking before excerpting, bounded regex workers, withholding results on failure, and boundary and failure checks. Test counts alone do not establish quality. Detailed planning documents are currently in Japanese.

Caching, SQLite AST storage, Git history, DB analysis, structural XML/HTML/Markdown parsing, OCR/document conversion, and interactive `review` are outside this completion scope. The [earlier concept review](docs/PRODUCT_REVIEW.md), [review design on hold](docs/DESIGN.md), and [document-to-design proposal](docs/REQUIREMENTS_RECOVERY.md) remain references. Planned features are not presented as implemented, and publication does not automatically start another development stage.

## Validation and contributions

```sh
python3 scripts/check_docs.py
python3 -m unittest discover -s tests -v
python3 scripts/run_search_trial.py
```

Check documentation, search/masking boundaries and failures, and the synthetic comparison separately. Search tests also require rg. Tests create synthetic fixtures in system temp and do not automatically delete them. A remote CI definition exists, but a successful remote run has not been confirmed.

See [contributing](CONTRIBUTING.md) for scope and validation, and the [security policy](SECURITY.md) for handling sensitive reports.

## License and publication

Licensed under MIT, with the notice `Copyright (c) 2026 Masaki Takemura`. See [LICENSE](LICENSE) for the authoritative terms. [External dependencies](THIRD_PARTY_NOTICES.md) and the [publication candidate reproduction report](docs/evaluation/PF_PACK.md) are available.

Private vulnerability reporting is enabled. Administrator notification confirmation, source push, and remote CI remain pending. See the [publication record](docs/evaluation/PF_PUBLISH.md). An explainable portfolio artifact and published, reusable OSS are distinct outcomes.
