# Contributing / 貢献ガイド

日本語・英語のIssueとPRを受け付ける方針です。開発版の検索CLIがあります。[検索契約](docs/SEARCH_CLI.md)と[マイルストーン](docs/MILESTONES.md)で変更範囲を確認してください。伏字CLIの[設計](docs/DESIGN.md)は保留中です。

Issues and pull requests may be written in Japanese or English. A development search CLI exists. Read its [contract](docs/SEARCH_CLI.md) and the [milestones](docs/MILESTONES.md) before changing scope. The [redaction design](docs/DESIGN.md) remains on hold.

## 変更範囲 / Scope

- 実際のログ共有で必要な一つの振る舞いと、その検証を変更単位にします。無関係な整形、依存追加、常駐・クラウド機能を混ぜないでください。
- Make each change address one concrete sharing task. Explain why the change is needed and how it will be checked.
- ライセンス採用が未確定のため、第三者のコードや検出ルールの取り込みは、その出典と利用条件を確認してから判断します。
- License adoption is pending. Do not import third-party code or rules without identifying their source and license.
- READMEの振る舞い・状態・制約を変える場合は、`README.md`と`README.en.md`を同じPRで更新してください。詳細計画は現在日本語です。
- Update both READMEs when changing behavior, status, or limitations. Detailed planning documents are currently in Japanese.

## 検証 / Validation

現在の文書検証（Python 3.11以上）：

```sh
python3 scripts/check_docs.py
python3 -m unittest discover -s tests -v
python3 scripts/run_search_trial.py
git diff --check
```

The checker validates local file links, required files, whitespace, and basic README structure. It does not validate semantic translation, external URLs, fragment anchors, or application behavior. Review those separately when relevant.

検索テストにはPATH上のrgが必要です。合成fixtureをシステムtempに残し、自動削除しません。実資料・秘密値は使わないでください。

Search tests require rg on PATH. Synthetic fixtures remain in system temp without automatic deletion. Never use real material or secrets as fixtures.

Rust案を採用した後の必要チェックは、固定したツールチェーンでの`cargo fmt --check`、`cargo clippy --locked --all-targets -- -D warnings`、`cargo test --locked`、`cargo build --release --locked`です。現在はCargoファイルがないため、これらを実施済みと記載しないでください。

For application changes, cover meaningful boundary cases and failures. Do not weaken expectations to make checks pass. Report local tests, CI, and actual user validation separately.

## 情報の扱い / Sensitive information

原文ログ、実案件名、内部ホスト名、ルールの実値、トークン、対応表をIssue・PR・CIへ添付しないでください。再現には構造を保った合成データを使います。漏えいにつながる問題は[セキュリティ方針](SECURITY.md)に従います。

Never attach real logs, client identifiers, internal hosts, live credentials, private rules, or alias maps. Use synthetic reproductions. Follow [SECURITY.md](SECURITY.md) for vulnerabilities.

## レビューと運用 / Review and maintenance

PRには問題、変更後の振る舞い、検証結果、未検証事項を記載します。強い保証や測定値には比較条件と根拠が必要です。担当者の同意数やテスト数を品質の証明にしません。

Describe the problem, resulting behavior, validation, and remaining limitations. Review the behavior and evidence rather than the contributor's identity. Response and merge times are not guaranteed.

公開、配布、リポジトリ設定、破壊的な操作はメンテナーの承認範囲に従います。PRのマージだけで未承認の配布や本番変更を起動する仕組みは追加しません。

Publication, distribution, repository settings, and destructive operations require the appropriate maintainer authorization. Do not add release automation that turns a merge into an unapproved distribution.
