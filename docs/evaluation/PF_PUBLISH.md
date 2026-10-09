# PF-PUBLISH：CI予行練習と公開の確認

実施日：2026-10-08。利用者がPF-3のソース公開・非公開報告設定・CI確認を承認した。ソース公開先は`mt4110/ops-whisper`のmain。2026-10-09に署名タグのpushと日英Releaseの公開も追加承認された。パッケージ・バイナリ配布、権限拡大、履歴改変は含めない。

## 現在の結果

**LinuxのCI予行練習は成功。非公開報告設定は有効。2026-10-09に通知設定を確認し、main公開とリモートCI確認を完了した。** [公開条件](../OSS_READINESS.md)と[SECURITY.md](../../SECURITY.md)の通知経路確認を完了した。

| 項目 | 結果 |
| --- | --- |
| ソース候補 | PF-2の55ファイルだけを新規作業ディレクトリへコピー。予行記録を追加した現候補は56ファイル |
| ローカル実行器 | act 0.2.89、Colima上のDocker、linux/arm64 |
| 予行イメージ | キャッシュ済みnode:20-bookwormを基に、予行用のsudoを加えたローカルイメージ。製品には同梱しない |
| イメージ識別 | sha256:6c28928a1d6ffff4c28c3def16b20c3e374a55b2858ad9564d170b0bf52f2609 |
| 実行環境 | Debian 12、Python 3.11.2、rg 13.0.0、arm64 |
| workflow | `.github/workflows/docs.yml`のdocsジョブをworkflow_dispatchで実行 |
| 文書検査 | 予行時27 Markdown成功。予行記録の追加後は28 Markdownを別途確認する |
| 検索・マスキング | 既存52テスト成功。期待値や安全条件の変更なし |
| 合成比較 | 正例・負例を含む6条件の期待結果を再現 |
| 全体終了 | act終了コード0、Job succeeded |
| 非公開報告 | 設定APIでenabled:true。管理者APIでAdvisoriesの取得成功。実報告送信は行わない |
| 管理者通知 | 2026-10-09のブラウザ操作でCustom → Security alertsを保存。個人設定のGitHub通知が有効。実報告送信・メール配送試験・CLI権限追加なし |
| 公開ソース／リモートCI | f79ac3a06dad3b38633a369f3379544f70cbcb0fをmainへ公開し、対象SHAのCI成功を確認 |

予行練習は公開予定の実装・試験・fixture・workflowをそのまま使った。DebianのローカルコンテナとGitHubのubuntu-latestランナーは異なる環境であり、予行成功をリモート成功と同一視しない。[actのランナー仕様](https://nektosact.com/usage/runners.html)も参照する。

## 実行とデータの境界

一時ファイルの自動削除を含む既存ラッパーは実行せず、同じactを直接使用した。予行用コピー、Git情報、イベントJSON、イメージとコンテナを保持する。CIキットのソースや非公開資料を本リポジトリへコピーせず、キット自体も変更しない。

actには空のenv/secret/var/inputファイルを明示し、GitHubトークンを渡していない。Dockerソケットをジョブへマウントせず、`--reuse`でジョブコンテナを保持した。候補へ実ログ・秘密・対応表を追加しない。入力は同梱の合成資料だけ。

actのcheckoutは候補のローカルコピーを使用した。固定SHAのactions/checkoutがGitHubランナーで実行できるかは、リモートCIで別に確認する。ホストへのPythonパッケージ追加はなく、sudoとrgの導入は予行用コンテナ内だけ。

## 残る確認と公開手順

1. 管理者がリポジトリのWatchでAll ActivityまたはCustom → Security alertsを選び、個人通知設定の配送方法を確認する。メール希望ならWatchingのEmailも選ぶ。[GitHubの公式手順](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)。架空の脆弱性報告は送らない。
2. 現候補を[明示一覧](publication-files.txt)と照合し、通常の追加コミットとしてmainへpushする。force push、reset、削除をしない。
3. 公開した対象SHAとファイル、MIT認識、非公開受付状態、対象SHAのリモートCIを確認する。
4. 実行URL・結果・環境を本書へ追記し、日英READMEとPF-3の状態を更新する。
5. 必要な確認が揃ったら初期開発を終了し、不具合修正と文書維持へ移る。

公開後の重大問題は回避策と修正版を準備する。履歴改変や公開物の削除は別途の具体的承認に従う。取得済みコピーの回収を約束しない。

## GitHubでの確認（2026-10-09）

- 公開ソース：[f79ac3a06dad3b38633a369f3379544f70cbcb0f](https://github.com/mt4110/ops-whisper/commit/f79ac3a06dad3b38633a369f3379544f70cbcb0f)。GitHubのmainと対象SHAが一致し、56ファイルの明示一覧と追跡ファイルが一致した。
- [リモートCI](https://github.com/mt4110/ops-whisper/actions/runs/37912411343)はsuccess。Ubuntu 24.04.5 amd64、rgパッケージ14.1.0-1。Pythonの厳密な版はworkflowの出力に記録していない。
- 文書28 Markdown、既存52テスト、正例・負例を含む合成6条件が成功。固定SHAのcheckoutを含む全ステップが成功した。実案件の便益・完全な秘密検出の証明ではない。
- GitHubはMITを認識。Private vulnerability reportingはAPIでenabled:true。ブラウザでCustom → Security alertsを保存し、個人通知のGitHub上での受信設定を確認。実報告送信やメール配送試験は行っていない。
- mainは保護なし、CODEOWNERSは@mt4110。承認された通常pushを行い、保護設定、権限、履歴は変更していない。
- PF-3を完了し、初期機能開発を終了する。今回の追加承認は`v0.1.0`の署名タグと日本語・英語のソースRelease。この記録を反映したタグ対象SHAでもCI成功を確認し、ローカル署名検証後にタグをpushする。Releaseの公開結果はGitHubのReleaseページで確認する。
