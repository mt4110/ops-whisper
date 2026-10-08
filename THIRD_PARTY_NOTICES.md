# Third-party dependencies / 外部依存

確認日：2026-10-08。現候補はソースのみで、Python・ripgrep・GitHub Actionsの本体、バイナリ、ライブラリを同梱しません。ops-whisper自身は[MIT](LICENSE)を採用し、外部依存の許諾条件は各依存の原文に従います。

This source candidate does not bundle Python, ripgrep, GitHub Actions, or their libraries/binaries. ops-whisper itself uses [MIT](LICENSE); external dependencies retain their own license terms.

| 依存 / Dependency | 使い方 / Use | 確認した版・根拠 / Version and source |
| --- | --- | --- |
| Python | 利用者が用意するインタープリターと標準ライブラリ。追加pip依存なし / User-provided interpreter and standard library; no pip dependencies | 実行版3.14.7、要求3.11以上。ライセンスの原文は[CPython 3.14.7 LICENSE](https://github.com/python/cpython/blob/v3.14.7/LICENSE) |
| ripgrep | PATH上の外部実行ファイルを子プロセスで起動 / External executable on PATH | 15.2.0。[COPYING](https://github.com/BurntSushi/ripgrep/blob/15.2.0/COPYING)にMIT / Unlicenseの選択を記載 |
| actions/checkout | リモートCIのcheckout。プロジェクトへコードを転載しない / Checkout in remote CI; not vendored | `11bd71901bbe5b1630ceea73d27597364c9af683`。[MIT LICENSE](https://github.com/actions/checkout/blob/11bd71901bbe5b1630ceea73d27597364c9af683/LICENSE) |

Pythonのライセンス文書には、Python本体と取り込まれたソフトウェアの条件が記載されています。ripgrepやPythonを将来配布物へ同梱する場合は、その時点の版と含める素材について再確認し、必要な本文・帰属を保持します。現ソースの公開だけを理由に外部依存のバイナリ配布まで承認済みと扱いません。

If a later distribution bundles these runtimes or components, review the exact included versions and retain the required licenses and attribution. Source-publication preparation does not authorize bundled runtime distribution.

現在のソース、標準ライブラリimport、固定workflowの確認範囲では、外部コードのvendoringや第三者の検出ルール集の取り込みはありません。組み込みの3ルールと合成資料は本リポジトリの作業で作成したものとして整理しています。メンテナーの採用指示に基づいてMITを配置し、第三者の帰属を変更しません。

The reviewed source imports, workflow, and file inventory contain no vendored external code or imported detector-rule collection. The three builtin rules and synthetic examples are treated as project-authored material; MIT was adopted following the maintainer’s instruction, without changing third-party attribution.
