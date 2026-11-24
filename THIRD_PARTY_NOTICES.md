# Third-party dependencies / 外部依存

確認日：2026-11-24。配布はソースのみで、外部ツールの本体、バイナリ、ライブラリを同梱しません。ops-whisper自身は[MIT](LICENSE)を採用し、外部依存の許諾条件は各依存の原文に従います。

The source distribution relies on separately installed tools. ops-whisper uses [MIT](LICENSE). External dependencies retain their own license terms.

| 依存 / Dependency | 使い方 / Use | 確認した版・根拠 / Version and source |
| --- | --- | --- |
| Python | インタープリターと標準ライブラリ / Interpreter and standard library | 開発・CIは3.15.2、実行条件は3.11以上。[CPython LICENSE](https://github.com/python/cpython/blob/v3.15.2/LICENSE) |
| ripgrep | PATH上の外部実行ファイル / External executable on PATH | CIは16.0.0。[COPYING](https://github.com/BurntSushi/ripgrep/blob/16.0.0/COPYING) |
| OSV-Scanner | コミット前とCIの依存検査 / Pre-commit and CI dependency scanning | CIは2.7.1。[Apache-2.0 LICENSE](https://github.com/google/osv-scanner/blob/v2.7.1/LICENSE) |
| actions/checkout | CIでソース取得 / Source checkout in CI | v7.0.1。[MIT LICENSE](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/LICENSE) |
| actions/setup-python | CIでPythonを設定 / Python setup in CI | v7.1.0。[MIT LICENSE](https://github.com/actions/setup-python/blob/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0/LICENSE) |
| github/codeql-action | CIでPythonを静的解析 / Static analysis in CI | v4.39.4。[Action license](https://github.com/github/codeql-action/blob/1bd86f2fdb4b86187fa4059f16f31a3202acc9ea/LICENSE)・[CodeQL terms](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md) |

Pythonのライセンス文書には、Python本体と取り込まれたソフトウェアの条件が記載されています。ripgrepやPythonを将来配布物へ同梱する場合は、その時点の版と含める素材について再確認し、必要な本文・帰属を保持します。現ソースの公開だけを理由に外部依存のバイナリ配布まで承認済みと扱いません。

If a later distribution bundles these runtimes or components, review the exact included versions and retain the required licenses and attribution. Source-publication preparation does not authorize bundled runtime distribution.

現在のソース、標準ライブラリimport、固定workflowの確認範囲では、外部コードのvendoringや第三者の検出ルール集の取り込みはありません。組み込みの3ルールと合成資料は本リポジトリの作業で作成したものとして整理しています。メンテナーの採用指示に基づいてMITを配置し、第三者の帰属を変更しません。

The reviewed source imports, workflow, and file inventory contain no vendored external code or imported detector-rule collection. The three builtin rules and synthetic examples are treated as project-authored material; MIT was adopted following the maintainer’s instruction, without changing third-party attribution.
