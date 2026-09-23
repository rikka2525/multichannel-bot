# Task: アンケート回答を安全にCSVエクスポートするローカルCLIを追加

手順は[AI_WORKFLOW.md](../../AI_WORKFLOW.md)、共通ルールは[CLAUDE.md](../../CLAUDE.md)、担当の詳細は[agents](../agents/)を参照する。

## 基本情報

- 関連Issue / 資料：https://github.com/rikka2525/multichannel-bot/issues/14 （[Feature] アンケート回答を安全にCSVエクスポートするローカルCLIを追加）
- 作業ブランチ：`feat/14-feedback-csv-export`
- 対象環境・前提：ローカル環境のみ。CI基準はGitHub ActionsのPython 3.12。外部サービス・APIとの連携なし。標準ライブラリのみ使用。
- 未確認事項：
  - エラーメッセージの具体的な文言・形式（Issueで「実装時に決定」と明記）。
  - 【推論】出力先に既存ファイルがある場合の扱い（上書き可否）はIssueに記載なし。実装時に安全側の方針を決め、PRに明記する。
  - 【推論】`exports/` などCSV出力先をgit管理外にするかはIssueに記載なし。個人情報を含み得るため`.gitignore`追加の要否をresearchで判断する。

## 目的

本リポジトリの管理者が、`survey_answers`テーブルに保存済みのアンケート回答（評価・自由記述・更新時刻）を、ローカルCLIで安全にCSVへ書き出し外部集計できるようにする。あわせて`/start`によるAI開発フローの最初の実戦テストとして、実コード・テスト・Security / Review・CIまで通す。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | `python tools/export_feedback.py --db <DB> --output <CSV>`で実行する | 指定SQLite DBからCSVを生成できる |
| R2 | 出力列 | `rating`, `comment`, `updated_at`を含む |
| R3 | 識別子を出力しない | `sender_key`や生ユーザーIDを出力しない |
| R4 | DBは読み取り専用 | エクスポート前後で元DBのデータが変わらない |
| R5 | 0件 | ヘッダー付きCSVを生成する |
| R6 | CSVエスケープ | カンマ・ダブルクォート・改行を含むコメントを正しく出力する（日本語含む） |
| R7 | Formula Injection対策 | `=`, `+`, `-`, `@`などで始まる自由記述が数式として解釈されない |
| R8 | 出力先の親ディレクトリ | 存在しなければ安全に作成する |
| R9 | 異常系 | 存在しないDB、必要テーブルがないDB、書き込み不可の出力先などを分かりやすく処理する（非ゼロ終了・簡潔なエラー） |
| R10 | ログ | 成功時・失敗時ともに秘密情報や回答本文を不要にログ・出力へ出さない |
| R11 | 文書 | READMEのCSV未実装記述を更新し、利用方法とプライバシー上の注意を記載する |

- 対象範囲：ローカルCLI（`tools/export_feedback.py`）、SQLite `survey_answers`の読み取り、CSV生成、自動テスト、README更新。
- 対象外：Web管理画面、Discord / TelegramコマンドからのCSV生成、自動送信、クラウドアップロード、定期エクスポート、生ユーザーIDの復元・出力、問い合わせ本文保存、DBスキーマ変更、deploy / release公開。
- 互換性・データ移行：DBは読み取り専用。スキーマ変更なし。既存機能への影響なし。

## 禁止事項

- 不要な大規模リファクタリング、不要な依存関係の追加、既存機能を壊す変更。
- 秘密情報の記載、テスト失敗の無視、テストを通すだけのハードコードや検証条件の弱体化。
- ユーザーの未コミット変更の取り消し、無断での実DB変更・外部サービスへの送信。
- 本タスクは`/start 14`により、作業ブランチでのgit add / commit、作業ブランチへのpush、PR作成までを許可されている。mainへの直接push、PRのmerge、deploy / release公開、Issueの手動close、他ブランチの削除は行わない。
- 案件固有の禁止事項：既存DBの破壊・更新、秘密情報・生ID・不要な個人情報のCSV出力、新規依存関係の追加。

## 完了条件

- [ ] 上記要件の受入条件を満たす。
- [ ] 必要なテストを追加し、全テストが成功している。最終変更に対応する結果を記録する。
- [ ] GitHub Actions（Python 3.12）が成功する。
- [ ] security / reviewの未解決Critical / Highが0件。
- [ ] その他の未解決・未確認事項、影響、対応方針を明示する。
- [ ] releaseが必要な文書と最終検証結果を確認し、リリース準備可能と判断する。
- [ ] 全変更ファイル・git diffを確認し、不要なファイルを残さない。
- 案件固有の追加条件・検証の適用除外と理由：ローカルPythonが3.12以外の場合、ローカル結果を「3.12で検証済み」と表現しない。

## Workflow

`research → implementation → test → security → review → release`

Critical / High、要件未達、テスト失敗があれば完了にせず差し戻す。修正後はtest → security → review → releaseを経て解消を確認する。

## 検証計画・最終報告

- 実行する確認：`python -m unittest discover -s tests -v`（全テスト）。追加テストで複数回答、空データ、コメントなし、日本語、カンマ、ダブルクォート、改行、Formula Injection候補文字、DB不存在、テーブル不存在、出力先エラー、元DB不変、既存機能の回帰を確認する。CIはGitHub Actions `Tests`（Python 3.12）。
- 実接続・データ変更などの副作用と実施条件：なし。テストは一時ディレクトリのSQLiteのみを使用し、`data/`の実DBには触れない。
- 最終報告：変更内容・ファイル、実行コマンド・対象状態・結果、未実行と理由、security / review結果、release準備可否、PR URL・CI状態、残課題、「Mergeは未実施」。
