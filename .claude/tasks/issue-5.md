# Task: test: Issue起動V1の動作確認

手順は[AI_WORKFLOW.md](../../AI_WORKFLOW.md)、共通ルールは[CLAUDE.md](../../CLAUDE.md)、担当の詳細は[agents](../agents/)を参照する。

## 基本情報

- 関連Issue / 資料：https://github.com/rikka2525/multichannel-bot/issues/5
- 作業ブランチ：chore/5-issue-workflow-test
- 対象環境・前提：Windows 11 / Python 3.12（READMEの動作確認環境）。CIはGitHub Actions `Tests`（ubuntu-latest, Python 3.12）
- 未確認事項：READMEへの追記位置はIssueに指定がない。前提として「既存記述を変えない位置に1行追加」とする（researchで決定）。

## 目的

Issue起動V1（`/start <Issue番号>`）で、Task作成→6Agentフロー→PR作成→CIまでが動作することを確認する。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | READMEに「Issue-driven workflow test」という1行を追加する | README.mdにその1行が存在し、差分は当該追加のみ |
| R2 | 既存機能は変更しない | コード・依存関係・設定の差分がない。既存テストが成功する |
| R3 | 必要な検証を実行する | 全テストの実行結果を記録する |
| R4 | `/start`でフローが開始され、Taskが作成される | `.claude/tasks/issue-5.md`が存在する |
| R5 | 6Agentフロー（research→implementation→test→security→review→release）が実行される | 各工程の結果がPR本文に記録される |
| R6 | PRが作成され、GitHub Actionsが成功する | mainへのPRが存在し、CIの状態を確認・報告する |
| R7 | mainへ直接pushしない、mergeしない | 作業ブランチのみpush。PRは未mergeで停止 |

- 対象範囲：README.md（1行追加）、本Taskファイル
- 対象外：本番機能の変更、デプロイ、merge
- 互換性・データ移行：なし

## 禁止事項

- 不要な大規模リファクタリング、不要な依存関係の追加、既存機能を壊す変更。
- 秘密情報の記載、テスト失敗の無視、テストを通すだけのハードコードや検証条件の弱体化。
- ユーザーの未コミット変更の取り消し、無断での実DB変更・外部サービスへの送信。
- mainへの直接push、Pull Requestのmerge、deploy / release公開、Issueの手動close。
- 案件固有：Issueに書かれていない機能・変更を追加しない。

## 完了条件

- [ ] 上記要件の受入条件を満たす。
- [ ] 全テストが成功している（最終変更に対応する結果を記録）。
- [ ] security / reviewの未解決Critical / Highが0件。
- [ ] その他の未解決・未確認事項、影響、対応方針を明示する。
- [ ] releaseが必要な文書と最終検証結果を確認し、リリース準備可能と判断する。
- [ ] 全変更ファイル・git diffを確認し、不要なファイルを残さない。
- 案件固有の追加条件・検証の適用除外と理由：なし（コード変更はないが、全テストは実行する）

## Workflow

`research → implementation → test → security → review → release`

親エージェントが順に依頼し、要件、変更範囲・差分、前工程の結果、未解決事項を引き継ぐ。
Critical / High、要件未達、テスト失敗があれば差し戻し、修正後はtest → security → review → releaseを再度通す。

## 検証計画・最終報告

- 実行する確認：`python -m unittest discover -s tests`（R2, R3）、`git diff` / `git diff --check`（R1）、PR作成後のCI状態確認（R6）
- 実接続・データ変更などの副作用と実施条件：なし
- 最終報告：変更内容・ファイル、実行コマンド・結果、security / review結果、PR URL、CI状態、残課題、Mergeは未実施
