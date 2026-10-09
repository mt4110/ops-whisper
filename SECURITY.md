# Security policy / セキュリティ方針

## 状態 / Status

開発版の検索CLIを実装しました。リリース・サポート対象バージョンはまだありません。検索は未指定では本文・周辺行・パス・検索語を表示します。明示した`--mask-rules`は一致ファイル全文に指定ルールを適用しますが、未知の秘密・パス・別名化・共有許可は保証範囲外です。[マスキング契約](docs/MASKING.md)を確認してください。検索語を秘密値にするとシェル履歴やプロセス一覧にも残り得ます。[検索の経路と限界](docs/SEARCH_CLI.md)を確認してください。匿名化、漏えい防止、物理消去は保証しません。

A development search CLI exists; there is no released or supported version yet. Search returns original text without an explicit masking policy. `--mask-rules` applies configured rules to complete matched files, but unknown secrets, paths, aliases, and sharing permission remain outside its guarantees. See the [masking contract](docs/MASKING.md); secret queries may also appear in shell history and process listings. Review the [search contract](docs/SEARCH_CLI.md). Complete anonymization, leak prevention, and physical erasure are not guaranteed.

## 非公開報告 / Private reporting

**2026-10-08にGitHub Private vulnerability reportingを有効化し、APIの`enabled:true`を確認しました。2026-10-09に管理者のWatch → Custom → Security alertsを保存し、個人通知設定のGitHub上での通知が有効であることを画面で確認しました。** 通知設定は確認済みです。実報告の配送試験は行っていません。

**GitHub private vulnerability reporting was enabled on 2026-10-08 and confirmed through the API. On 2026-10-09, Custom Security alerts were saved and GitHub notification delivery was confirmed in the administrator’s settings.** Notification configuration is verified; actual report delivery has not been tested.

[Security Advisories](https://github.com/mt4110/ops-whisper/security/advisories)の「Report a vulnerability」から非公開で報告してください。実報告を送信する試験は行っていません。

Use “Report a vulnerability” on [Security Advisories](https://github.com/mt4110/ops-whisper/security/advisories) for a private report. No test report was submitted.

漏えい経路・悪用手順・機密情報を公開Issueに書かないでください。通知のためには、このリポジトリのWatchでAll ActivityまたはCustomのSecurity alertsを選び、個人通知設定で配送方法を確認します。[GitHubの公式手順](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)を参照してください。

Do not disclose exposure paths, exploitation details, or sensitive data in public issues. Administrators should watch All Activity or Custom Security alerts and confirm delivery preferences in their personal notification settings. See the [GitHub instructions](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

## 報告内容 / Report contents

非公開報告には、影響を受ける版・OS、期待した振る舞い、実際の振る舞い、合成データでの最小再現、推定される影響を含めます。原文ログ、実トークン、案件名、実ルール、置換対応表は不要です。

Include the affected version and OS, expected and observed behavior, a minimal synthetic reproduction, and potential impact. Do not include real logs, live tokens, client data, private rules, or alias mappings.

自分が管理する環境だけで検証し、他人の機密情報や稼働環境へアクセスしないでください。受付・修正日数、報奨金、すべての報告への修正を約束しません。

Test only systems you control. There is no promised response deadline, fix deadline, or bounty program.

## 漏えいを疑う場合 / Suspected exposure

秘密値を共有済みの場合は、マスキング済みと考えて放置せず、該当サービスと組織の失効・再発行・事故対応手順に従ってください。ops-whisperは秘密値の失効や共有先の削除を自動実行しません。

If a credential may have been shared, follow the relevant service and organization's revocation, replacement, and incident procedures. ops-whisper will not revoke credentials or delete data from recipients automatically.

設計上の経路と限界は[脅威モデル](docs/THREAT_MODEL.md)を参照してください。
