# GitHub公開準備

## 候補

- 推奨リポジトリ名：`multichannel-bot`
- 代替：`multichannel-bot-framework`、`python-multichannel-bot`
- 説明文：Python bot framework with shared conversation logic, Discord and Telegram adapters, and SQLite persistence. WhatsApp integration pending live validation.
- トピック：`python`, `discord-bot`, `telegram-bot`, `chatbot`, `sqlite`, `flask`, `portfolio`, `adapter-pattern`

## 公開境界

ローカルで公開用ファイルとGitの候補一覧を確認するところまで準備します。GitHubへのリポジトリ作成、push、公開設定変更はユーザーの明示的な許可後に実施します。GitHubアカウント内に同名リポジトリがあるかは今回未確認です。

公開対象はこの`multichannel-bot`フォルダだけです。実接続用フォルダや親フォルダ全体をアップロードしないでください。

## 秘密情報と保守

`.env.example`は秘密値を空欄にしています。`.env`、許可ID、実データのDB、ログ、仮想環境、キャッシュ、鍵、バックアップを公開対象から除外します。テストに含まれる番号・トークンはダミーです。

`.gitignore`は既に追跡されたファイルや過去コミットから秘密を削除しません。将来誤って公開した場合は認証情報の失効・再発行と履歴対処が必要です。スクリーンショットを追加するときもID、アイコン、実会話、トークンを確認してください。

ライセンスは権利者と再利用許可の方針が未指定のため追加していません。公開前に採用する場合は著作権表記を確認してください。ライセンスなしの公開を「自由に再利用可能」とは案内しません。

公開前にDiscordの表示名を確認し、READMEの実績と未検証範囲を確認してください。依存関係の脆弱性監査・本番負荷試験は今回の実施範囲に含みません。
