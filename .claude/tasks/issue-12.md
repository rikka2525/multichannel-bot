# Task: test: PR fix workflow V1の動作確認

手順は[AI_WORKFLOW.md](../../AI_WORKFLOW.md)、共通ルールは[CLAUDE.md](../../CLAUDE.md)、担当の詳細は[agents](../agents/)を参照する。

## 基本情報

- 関連Issue / 資料：https://github.com/rikka2525/multichannel-bot/issues/12
- 作業ブランチ：chore/12-pr-fix-workflow-v1-check
- 対象環境・前提：Windows 11 / PowerShell。ローカルPythonは3.14.6、CI基準はGitHub ActionsのPython 3.12。秘密値は扱わない。
- 未確認事項：
  - Python 3.12でのテスト結果とGitHub Actionsの結果（ローカルは3.14.6のみ。PR作成後にCIで確認する）。
  - 追記行は箇条書き記号・空行なしのため、Markdown描画上は直前の箇条書きの続き行になる。Issue指定の文言・位置を優先して修正しない（既知）。
- 前提（推論）：追記先のREADME.mdは既存行がCRLFのため、追記行も同じ改行コードに揃える。

## 目的

`/fix <PR番号>`のV1動作を確認するため、検証用PRを`/start`で作成できる状態にする。README末尾へ確認用の1行を追加した最小のPRを作る。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | README末尾に`PR fix workflow V1 test - before review`の1行を追加する | README.mdの最終行がその文字列で、他の行に差分がない |
| R2 | 既存機能を変更しない | README.md以外のアプリケーションコードに差分がない |
| R3 | 必要な検証を実行する | 既存テストが成功し、CIの結果を確認している |

Issueの受入条件（PR作成後に確認する項目）：

- `/start <Issue番号>`で検証用PRを作成できる
- PRレビューコメントを`/fix <PR番号>`が取得できる
- 同じPRのhead branch上で修正する
- 新しいPRを作成しない
- 修正後にCI完了まで確認する
- PR本文へ最新結果を反映する
- mainへ直接pushしない
- mergeしない

`/fix`に関する項目は本タスクの後続作業で確認する。本タスクで満たすのは、`/start`によるPR作成までとする。

- 対象範囲：README.mdへの1行追加、本Task文書
- 対象外：本体機能の変更、deploy、merge
- 互換性・データ移行：なし

## 禁止事項

- 不要な大規模リファクタリング、不要な依存関係の追加、既存機能を壊す変更。
- 秘密情報の記載、テスト失敗の無視、テストを通すだけのハードコードや検証条件の弱体化。
- ユーザーの未コミット変更の取り消し、無断での実DB変更・外部サービスへの送信。
- mainへの直接push、Pull Requestのmerge、deploy / release公開、Issueの手動close。
- `/start`の手動実行で許可された範囲（作業ブランチのcommit・push、PR作成）を超える操作。

## 完了条件

- [ ] 上記要件の受入条件を満たす。
- [ ] 既存テストが成功している。最終変更に対応する結果を記録する。
- [ ] security / reviewの未解決Critical / Highが0件。
- [ ] その他の未解決・未確認事項、影響、対応方針を明示する。
- [ ] releaseが必要な文書と最終検証結果を確認し、リリース準備可能と判断する。
- [ ] 全変更ファイル・git diffを確認し、不要なファイルを残さない。
- [ ] PR作成後、CIの完了を確認してPR本文へ反映する。
- 案件固有の追加条件・検証の適用除外と理由：なし。変更は文書のみだが、CIの基準に合わせて既存テストを実行する。

## Workflow

`research → implementation → test → security → review → release`

親エージェントが順に依頼し、要件、変更範囲・差分、前工程の結果、未解決事項を引き継ぐ。

## 検証計画・最終報告

- 実行する確認：`python -m unittest discover -s tests`（R3）、`git diff` / `git diff --check`でREADME.mdの差分が1行追加のみであること（R1・R2）
- 実接続・データ変更などの副作用と実施条件：なし
- 最終報告：`/start`の最終報告項目に従う。
