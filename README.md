# ops-whisper

[English](README.en.md)

**原文の位置・一致件数・省略を残し、返す量を制限する、小さなローカル検索CLI。**

既存のripgrepでテキストを検索し、行番号付きの抜粋をテキストまたはJSONで返します。明示したTOMLで、一致ファイルの全文へマスキングを適用してから抜粋できます。コードやログを読む際に、抜粋から元ファイルへ戻り、表示されなかった一致があるか確認するための補助ツールです。

## 現在の状態

**ポートフォリオ用の小規模CLIとして、機能をここで区切ります。** 検索、本文マスキング、固定合成ログでの比較はローカル検証済みです。PF-1「再現して説明できるポートフォリオCLI」までを完成範囲とし、OSS公開候補の整備と公開は別の段階です。配布版・グローバルインストールは未提供です。

macOS arm64、Python 3.14.7、rg 15.2.0で確認しています。Linuxの予行練習（Debian 12 arm64、Python 3.11.2、rg 13.0.0）も成功しました。GitHubのリモートCIは未確認、Windowsは未検証です。実案件での時間短縮、トークン費用の削減、秘密の検出精度は実証していません。

## 使い方

Python 3.11以上とPATH上の`rg`が必要です。チェックアウト内から実行し、追加のPythonパッケージは不要です。

```sh
./ops-whisper search 'host=' --root examples/input.synthetic.txt --context 0
./ops-whisper search 'host=' --root examples/input.synthetic.txt --mask-rules examples/masking.synthetic.toml --json
./ops-whisper search 'status=503' --root examples/input.synthetic.txt --context 0 --max-results 5 --max-chars 2000 --json
./ops-whisper search 'SearchError' --root ops_whisper --glob '*.py' --max-results 5
./ops-whisper search --help
```

検索語は大文字小文字を区別するリテラル文字列で、`--root`は必須です。既定は前後2行、優先する一致20行、応答全体8000文字。全件数を得るため検索対象を最後まで読み、返す量を制限します。抜粋は重要度順でも代表標本でもありません。全一致を返したい場合や単純な絞り込みには、直接rgを使う方が簡単なことがあります。[検索契約](docs/SEARCH_CLI.md)でJSON・終了コード・範囲と上限を説明しています。

`--mask-rules`を指定すると、組み込みルールと追加正規表現を一致ファイルの全文へ適用します。改行と文字位置を保って伏せた後、抜粋します。`redacted:true`は設定適用の記録であり、全秘密の検出や共有許可を意味しません。未指定では原文を返します。root・ファイル名はマスクせず、未知の秘密や過剰マスクもあり得ます。[マスキング契約](docs/MASKING.md)を確認し、共有前に出力を見直してください。

再帰探索では隠しファイルを除外し、リンクを辿りませんが、肯定globはignoreされた通常ファイルを含め得ます。明示ファイルや変更中の入力を隔離するサンドボックスではありません。

## 合成データで試す

実ログや業務資料を用意する必要はありません。架空のインフラログと事前に定義した期待結果を同梱しています。

```sh
# 広い検索では、後半の障害・復旧記録が抜粋に入りません。
./ops-whisper search 'service=demo-api' --root examples/search-trial/infra.synthetic.txt --context 0 --max-results 5 --max-chars 3000 --json
# 問いを要求IDと試行へ絞り、必要な観測行を回収します。
./ops-whisper search 'request=demo-42 attempt=' --root examples/search-trial/infra.synthetic.txt --context 1 --max-results 10 --max-chars 6000 --mask-rules examples/search-trial/focused.toml --json
# 保持と欠落、未知の秘密、過剰マスクを含む6条件を照合します。
python3 scripts/run_search_trial.py
```

広い検索は313一致のうち5行を返し、必要な障害・再試行・復旧の行を省略します。絞った検索では根拠の4観測行を返します。この4行には再収集された重複があり、異なる試行は3です。検索一致数を障害回数と読み替えないでください。

比較スクリプトの成功は、既知の失敗例も期待どおり再現したという意味です。共有安全性の認証ではありません。狭い検索の比較ではrgテキスト1383文字、マスクJSON2894文字で、JSONが常に小さくなるという前提も成立しません。測定条件と限界は[合成比較の記録](docs/evaluation/SEARCH_SYNTHETIC_TRIAL.md)にあります。

## 完成目標と設計

| 段階 | 到達すると何になるか | 現在 |
| --- | --- | --- |
| PF-0 | 動作する小規模CLI | ローカル完了 |
| PF-1 | 再現して説明できるポートフォリオCLI | ローカル完了・今回の機能開発の区切り |
| PF-2 | 第三者が試せるOSS公開候補 | ローカル完了・MIT採用済み |
| PF-3 | ソース公開済みのポートフォリオOSS | 公開承認済み・CI予行成功、通知確認とリモートCIは残作業 |

[マイルストーン](docs/MILESTONES.md)に各段階の完了条件と終了地点、[実行タスク](docs/TASKS.md)に残作業、[公開準備](docs/OSS_READINESS.md)に公開条件を記載しています。設計を説明する根拠は、検索範囲と出力上限、全文から抜粋へのマスキング、regexワーカーの期限、失敗時に結果を出さない処理と、その境界・異常系の検証です。テスト件数だけを品質の証明にはしません。

キャッシュ、SQLite AST、Git履歴、DB解析、XML・HTML・Markdownの構造解析、OCR・文書変換、対話式`review`は今回の完成条件に含めません。[過去の構想と判断](docs/PRODUCT_REVIEW.md)、[保留したreview設計](docs/DESIGN.md)、[資料から暫定設計を作る案](docs/REQUIREMENTS_RECOVERY.md)は参考として保管しています。将来の機能を実装済みと表示せず、公開後も自動的に次の開発段階へ進みません。

## 検証と貢献

```sh
python3 scripts/check_docs.py
python3 -m unittest discover -s tests -v
python3 scripts/run_search_trial.py
```

文書検証、検索・マスキングの境界と異常系、合成比較を別々に確認します。検索試験にはrgも必要です。テストは合成fixtureをシステムtempへ作り、自動削除しません。リモートCIの定義はありますが、成功を確認したとは扱いません。

変更範囲と検証方法は[貢献ガイド](CONTRIBUTING.md)、秘密を含む報告の扱いは[セキュリティ方針](SECURITY.md)を参照してください。

## ライセンスと公開

MITライセンスを採用しています。著作権者表記は`Copyright (c) 2026 Masaki Takemura`です。正式な許諾本文は[LICENSE](LICENSE)を参照してください。[外部依存の整理](THIRD_PARTY_NOTICES.md)と[公開候補の再現記録](docs/evaluation/PF_PACK.md)も用意しています。

非公開脆弱性報告は有効化済みです。管理者の通知設定確認、ソースのpushとリモートCIの確認を残しています。[公開の記録](docs/evaluation/PF_PUBLISH.md)を参照してください。ポートフォリオとして説明できることと、OSSとして公開・再利用できることを区別します。
