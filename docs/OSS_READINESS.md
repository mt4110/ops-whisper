# ops-whisper OSS公開準備

更新日：2026-10-08。**PF-1「再現して説明できるポートフォリオCLI」はローカル完了。PF-2のOSS公開候補もローカル完了。PF-3は承認済み、Linux予行成功・通知確認待ち。** 実装済みの小さなsearchを公開するための準備を記す。保証済みのセキュリティ基盤として扱わない。

現在の到達目標は[マイルストーン](MILESTONES.md)、残作業は[PF-PACK / PF-PUBLISH](TASKS.md#pf-pack)。[PF-PACKのローカル再現と準備](evaluation/PF_PACK.md)は完了し、利用者の氏名指定でMITを採用し、PF-2はローカル完了。事業上の需要や実案件での便益の実証、DR/IR/OWの実務試験は、このポートフォリオの公開条件にしない。未知の秘密や根拠の欠落等の制約は、公開時にも明示する。

## 今回準備したセット

| ファイル | 役割 | 状態 |
| --- | --- | --- |
| README.md / README.en.md | 実装済み検索・TOMLマスキング、合成デモ、完成段階、限界 | ローカル整備済み |
| ops-whisper / ops_whisper / tests | 既存rgを使う最小検索、TOMLマスキング、合成テスト | macOSでローカル確認。未リリース |
| docs/evaluation/SEARCH_SYNTHETIC_TRIAL.md / examples/search-trial / scripts/run_search_trial.py | 固定合成ログと独立した期待結果による6条件の比較 | ローカル確認。実ログ・クラウドへのアクセスなし |
| docs/MASKING.md / examples/masking.synthetic.toml | 位置を保つ本文マスキングとTOML例 | ローカル合成検証。未知の秘密・パスは対象外 |
| docs/SEARCH_CLI.md | 範囲、上限、JSON、省略、失敗時の契約 | 実装に対応。明示TOMLによる本文マスキングを追加 |
| docs/PRODUCT_REVIEW.md | 現在のポートフォリオ判断と、以前の実務・事業仮説 | 商業性と実案件の便益は未検証 |
| docs/TASKS.md | PF完成・公開タスク、完了したSR/MS、保留DR/LG/IR/OW | PF-DOC完了。PF-PACKローカル完了・MIT採用済み。PF-PUBLISHはLinux予行成功・通知確認待ち |
| docs/evaluation/PF_PACK.md / publication-files.txt | 55ファイルの明示候補と、ソース一式だけでの再現記録 | ローカル再現成功。公開・設定変更は未実施 |
| THIRD_PARTY_NOTICES.md | Python・rg・CI用checkoutと、同梱しない依存の整理 | 対象版の一次資料で確認 |
| docs/REQUIREMENTS_RECOVERY.md | 混在資料から要件・暫定設計への手順と実装判断 | 机上整理。形式変換・OCRは未実施 |
| docs/evaluation/REQUIREMENTS_RECOVERY_TEMPLATE.md | 資料・根拠・要件・判断・設計の対応を記録する型 | 未記入。実案件情報は保管場所を分ける |
| docs/INFRA_REPORT_WORKFLOW.md | 結論と証拠を対応付ける手順 | 一件で試す計画 |
| docs/evaluation/INFRA_REPORT_EXAMPLE.md | 支持・制約・矛盾を残した記入例 | 全て架空の資料 |
| docs/evaluation/INFRA_REPORT_TRIAL.md | 合成資料での報告編集・マスキング・確認記録 | 実案件・時間短縮・需要の検証ではない |
| examples/infra-report.submission.synthetic.md | 変換前の架空識別子・認証値を含めない提出用サンプル | 内部確認のみ。外部提出は未実施 |
| docs/REVIEW_FLOW.md | 最小操作の紙上案 | 利用者試験は未実施 |
| docs/evaluation/INFRA_REPORT_TEMPLATE.md | 分析結果と証拠を対応付ける記録型 | 新規実装を増やさない代替案 |
| docs/DESIGN.md | 入出力・レビュー・変換の契約 | 設計案 |
| docs/MILESTONES.md | PF-0〜PF-3の到達目標・完了条件・終了地点と、以前の計画 | PF-2までローカル完了。PF-3はLinux予行成功・通知確認待ち |
| docs/THREAT_MODEL.md | データ経路と残るリスク | 設計要件 |
| CONTRIBUTING.md | 変更範囲、検証、日英文書 | 準備済み |
| SECURITY.md | 非公開報告と機密情報の取扱い | 窓口は有効化済み。通知設定は確認待ち |
| CODE_OF_CONDUCT.md | 参加と運用方針 | 専用非公開連絡先は未設定 |
| CHANGELOG.md | 未リリースの変更記録 | 準備済み |
| .github/ISSUE_TEMPLATE | 不具合、提案、報告方針へのリンク | 合成再現だけを求める |
| .github/pull_request_template.md | 問題、結果、検証、制約 | 準備済み |
| .github/CODEOWNERS | レビュー対象と責任 | 所有者mt4110を案として指定 |
| .github/workflows/docs.yml | 文書、合成検索テスト、SR-02再現比較 | actのLinux予行成功。リモート未実行 |
| .editorconfig / .gitignore | 文字組みと機密作業物の除外 | 無視設定は漏えい防止保証ではない |
| examples | 架空のログ・ルール・出力 | 検索マスキング例はローカル確認。旧reviewの変換例は未実装 |
| LICENSE / docs/license/MIT-LICENSE.txt | Masaki Takemuraを著作権者表記とするMIT本文と参照コピー | 採用済み。正式本文はルートLICENSE |

CODEOWNERSは自動で必須レビューを強制しない。ブランチ保護の設定は未変更。Dependabot、ラベル、Discussions、配布ワークフローなどの追加は、必要性が生じた段階で判断する。

## ライセンス判断

利用者の採用指示と氏名指定に基づき、[MITの正式本文](../LICENSE)を配置した。著作権表記は`Copyright (c) 2026 Masaki Takemura`。[MIT本文と条件](https://opensource.org/license/mit)、[外部依存の整理](../THIRD_PARTY_NOTICES.md)を参照する。

現在はソースのみの候補で、パッケージメタデータはない。日英READMEと候補一覧をLICENSEに同期した。外部依存の許諾条件は独自のMITへ置き換えず、第三者の帰属を保持する。

## セキュリティ報告窓口

利用者のPF-3承認に基づき2026-10-08に有効化し、GitHub APIの`enabled: true`を確認した。受付URLとSECURITY.mdを更新した。管理者の個人通知設定は確認待ちであり、公開条件として残す。[GitHubの設定手順](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)

公開Issueへ機密や悪用手順を誘導しない。テンプレートのリンクはSECURITY.mdへ向け、通知受信の確認を済んだと扱わない。

## CI方針

現在のworkflowは、空白検証を含む文書チェッカー、合成検索テスト、SR-02の再現比較。Python 3.11以上の標準ライブラリを使い、検索テスト用のrgはUbuntuのパッケージから取得する定義。act予行ではDebianのrg 13.0.0で52テストと合成6条件が成功した。GitHubランナーで取得する版・結果は未確認。`contents: read`、checkout資格情報を残さない設定、時間上限、checkoutの完全SHA固定を採用する。秘密値、実ログ、実ルール、対応表を入力・artifact・キャッシュに使わない。fixtureはランナーのtemp配下に作り、テストから削除しない。

PRの確認には`pull_request`を使い、特権的な`pull_request_target`で未信頼コードを実行しない。自動コメントや公開に必要な書き込み権限を初期CIへ加えない。[GitHub Actionsの安全指針](https://docs.github.com/en/actions/reference/security/secure-use)

以前のreview用Rust案のツールチェーンや検出器選定は、現searchの公開準備には含めない。Windows等の追加対応は、別途選んだ範囲で検証した場合だけ記載する。

## 初期公開チェックリスト

- [x] PF-2の公開対象と再現記録が揃い、既存の機能・合成デモ・失敗条件をソース一式だけで試せる。
- [x] SR-02の制約を日英READMEへ反映し、実ログなしで用途と限界を説明できる。実務の便益・完全な秘密検出を保証しない。
- [x] 利用者の指示でMITと著作権者表記を確定し、依存の許諾条件・帰属を整理した。
- [ ] 非公開報告窓口を有効化し、受付と通知を確認した。
- [ ] 原文ログ、実ルール、トークン、対応表が公開物とGit履歴にない。
- [ ] 日英READMEの状態とコマンドが実装・リリースに一致する。
- [ ] 対応OS、入力上限、検出対象、検出漏れ、部分出力の限界を明示した。
- [ ] 必要なローカル検証とリモートCIを区別して記録し、PF-3完了前に対象ソースのリモートCI成功を確認した。
- [ ] CODEOWNERSとブランチ保護の運用を確認した。
- [ ] 版、公開先、内容、利用者の明示承認を記録した。

## 配布と復旧

最初の公開はソースのみでもよい。バイナリ配布、Homebrew、crates.io、署名・公証は初期OSS公開とは別の負担と承認範囲を持つ。需要が未確認なら先に追加しない。

公開後に重大な問題が見つかった場合は、配布ページで制約と回避策を明示し、修正版と変更履歴を準備する。公開物やGit履歴を勝手に削除・改変せず、必要な撤回操作は対象と影響を示して承認を得る。既に取得されたコピーを回収・消去できるとは説明しない。

## 今回の境界

PF-PACKに続きPF-3のmainへの通常commit/push、非公開脆弱性報告の有効化、CI確認も利用者が承認した。通知設定確認という既存の公開条件を守る。追加機能、実ログ取得、タグ・Release・パッケージ配布、権限拡大や履歴改変は含めない。各チェック欄は、次の操作への承認を代行しない。
