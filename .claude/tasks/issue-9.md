# Task: test: Issue起動V1.1の動作確認

## 基本情報

- 関連Issue / 資料：https://github.com/rikka2525/multichannel-bot/issues/9
- 作業ブランチ：chore/9-verify-start-v1-1
- 対象環境・前提：Windows 11 / PowerShell。CI基準はGitHub ActionsのPython 3.12（前提：`.github/workflows/tests.yml`の記載による）。ローカルPythonは実測して記録する。
- 未確認事項：なし（Issueの要件に実装を左右する曖昧さはない）

## 目的

Issue起動V1.1（`/start <Issue番号>`）の改善点が、Issue取得からPR作成・CI待機・PR本文反映までAI開発フロー通りに動作することを確認する。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | READMEに「Issue-driven workflow V1.1 test」という1行を追加する | README.mdにその1行が追加されている |
| R2 | 既存機能は変更しない | READMEの1行追加と本Task文書以外の変更がコード・設定にない |
| R3 | 必要な検証を実行する | 全テストを実行し結果を記録する |
| R4 | `/start <Issue番号>`でAI開発フローが開始される | research→…→releaseが順に実施される |
| R5 | 作業ブランチが`--no-track`で作成される | 作成直後にupstream未設定 |
| R6 | push後のupstreamが`origin/<作業ブランチ>`になる | `git branch -vv`で確認 |
| R7 | Local Pythonのバージョンを記録する | PR本文にLocal runtimeを記載 |
| R8 | CI baselineのPython 3.12を区別して記録する | PR本文にCI baselineを別記 |
| R9 | GitHub Actionsの完了まで待つ | `gh pr checks --watch`で完了確認 |
| R10 | CI結果がPR本文へ反映される | PR本文にCI結果とURLを記載 |
| R11 | mainへ直接pushしない / mergeしない | PRは未merge、mainは変更なし |

- 対象範囲：README.mdへの1行追加、本Task文書、PR作成。
- 対象外：本番機能の変更、deploy、merge。
- 互換性・データ移行：なし。

## 禁止事項

- 不要な大規模リファクタリング、不要な依存関係の追加、既存機能を壊す変更。
- 秘密情報の記載、テスト失敗の無視、テストを通すだけのハードコードや検証条件の弱体化。
- ユーザーの未コミット変更の取り消し、無断での実DB変更・外部サービスへの送信。
- `/start`の明示許可範囲外の操作（mainへのpush、PR merge、deploy、Issueのclose）。
- 案件固有：ローカルPython結果を「Python 3.12で検証済み」と表現しない。CI未完了・失敗をローカル成功だけで成功扱いしない。

## 完了条件

- [ ] 上記要件の受入条件を満たす。
- [ ] 全テストが成功している（Local runtimeとCI baselineを区別して記録）。
- [ ] security / reviewの未解決Critical / Highが0件。
- [ ] その他の未解決・未確認事項、影響、対応方針を明示する。
- [ ] releaseが必要な文書と最終検証結果を確認し、リリース準備可能と判断する。
- [ ] 全変更ファイル・git diffを確認し、不要なファイルを残さない。
- 案件固有の追加条件・検証の適用除外と理由：なし。README1行のみの変更だがアプリテストは実行する。

## Workflow

`research → implementation → test → security → review → release`

## 検証計画・最終報告

- 実行する確認：`python --version`、`python -m unittest discover -s tests`、`git diff` / `git diff --check`、GitHub Actions（Python 3.12）の結果。
- 実接続・データ変更などの副作用と実施条件：なし（外部サービス接続なし）。
- 最終報告：`/start`スキル§7の項目に従う。Mergeは未実施と明記。
