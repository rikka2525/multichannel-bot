# 架空のアンケート回答 → CSV → 表で確認

MultiChannel Botの既存 `tools/export_feedback.py` で、保存済みのアンケート回答を3列CSVへ取り出す例です。入力・識別子・日時はすべて架空です。Bot起動・認証情報・外部API・追加パッケージは不要です。

**[完成CSVを開く](fictional-feedback.csv)** · [入力JSON](fictional-input.json) · [DB作成用スクリプト](create_demo.py)

## 完成例

| rating（評価） | comment（コメント） | updated_at（UTC） |
| --- | --- | --- |
| 5 | 案内がわかりやすかった | 2026-10-01 09:00:00 |
| 4 | 料金, 手順を確認できた | 2026-10-01 09:05:00 |
| 3 |  | 2026-10-01 09:10:00 |
| 4 | '=1+1 | 2026-10-01 09:15:00 |
| 5 | 案内がわかりやすかった | 2026-10-01 09:20:00 |

上の表はCSVの値を記載したMarkdown表です。画面のスクリーンショットではありません。
コメント未入力は空欄、カンマ入りのコメントは1セルとして出力されます。`=1+1` には既存CLIが先頭に `'` を付けます。重複するコメントはそのまま残ります。

この機能はBotのアンケートDBから `rating`・`comment`・`updated_at` を取り出すものです。任意CSVの整形、重複除去、表記統一は実装していません。

## ローカルで再現する

Python 3.12を用意し、リポジトリのルートで実行します。標準ライブラリだけを使います。

```powershell
py -3.12 examples/feedback-csv/create_demo.py
py -3.12 tools/export_feedback.py --db examples/feedback-csv/fictional-feedback.db --output exports/fictional-feedback.csv
```

1行目は入力JSONの5回答から、既存のアンケートテーブルと同じ構造の架空DBを作ります。Bot経由の会話入力を再現するものではありません。
2行目は既存CLIでCSVを出力します。CSVはUTF-8（BOM付き）、更新日時はUTCです。識別子は出力しません。

DB作成用スクリプトは既存DBを上書きしません。2回目以降は作成済みの架空DBを使い、出力先を `exports/fictional-feedback-2.csv` など別名にしてください。既存CLIも、既定ではCSVの上書きを拒否します。

## 表計算で確認する

Google Sheetsの新規シートでCSVをインポートし、「テキストを数値、日付、数式に変換する」をオフにして確認できます。日本語、3列5回答、空欄、日時の文字列を確認してください。

この例は、ユーザー操作でGoogle Sheetsへ変換オフでインポートし、3列5回答・日本語・日時・空欄の表示を確認しています。数式の自動変換オンやExcel実機での動作を保証する確認ではありません。CSVの先頭文字対策についても、すべての表計算ソフト・入力形式での安全を保証するものではありません。

## 検証範囲

- 2026-10-06、Windows / Python 3.12.14で、この架空入力から出力CSVへの全セル一致とBOMを確認。
- 出力前後で架空DBのSHA-256が一致し、DBのジャーナル等が残らないことを確認。
- 既存CSVテスト `test_export_feedback.py` は42件成功。Botの実接続は今回の対象外。
- 既存CLIの取得・確認版は [`83cd18e`](https://github.com/rikka2525/multichannel-bot/tree/83cd18e7ae99e545c42c4c0c8a08e69491777658)。CLI自体はこの例のために変更していません。

掲載CSVだけが公開用の架空データです。本物のDB・回答CSV・トークンは公開しないでください。
