# Task: fix PR #13

手順は[AI_WORKFLOW.md](../../AI_WORKFLOW.md)、共通ルールは[CLAUDE.md](../../CLAUDE.md)、担当の詳細は[agents](../agents/)を参照する。

## 基本情報

- PR：#13 chore: PR fix workflow V1の動作確認用にREADMEへ1行追加
- PR URL：https://github.com/rikka2525/multichannel-bot/pull/13
- base branch：main
- head branch：chore/12-pr-fix-workflow-v1-check
- head SHA（着手時）：1ba03f787e697da5a67f7029be12bc283fcb2891
- linked Issue：#12（PR本文は`Refs #12`。closingIssuesReferencesは空）
- 対象環境・前提：Windows 11 / PowerShell、ローカルPython 3.14.6、CI baselineはGitHub ActionsのPython 3.12。
- 取得したreview input：reviews 0件、inline review comments 0件、review threads 0件、PR conversation comment 1件、CI failure 0件（`Python 3.12 unit tests`は成功）。

## 修正対象

| ID | Source | 内容 | 修正方針 | 検証方法 | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | PR conversation comment（オーナー rikka2525、2026-09-21T15:50:44Z、https://github.com/rikka2525/multichannel-bot/pull/13#issuecomment-5763355120） | READMEの`PR fix workflow V1 test - before review`を`PR fix workflow V1 test - fixed`に変更する | README.md 123行目の文言のみを置換する。CRLF・行数・他の行は変えない | `git diff`が該当1行の置換のみ、`git diff --check`、全行CRLF、既存テスト、CI | 実装・ローカル検証済み（push後のCI確認待ち） |

分類の記録：

- F1：必須修正（明示的な修正要求）。
- PR本文Remaining concernsの「追記行がMarkdown描画上、直前の箇条書きの続き行になる（Low）」：対象外。PR本文に「修正しない（既知）」と明記されている。
- PR本文Remaining concernsの「`/fix`に関するIssue受入条件」：対象外。コード・文書変更で解消する項目ではない。
- CI failure：なし。

## 目的

PR #13のオーナーコメントの要求に従い、READMEの確認用1行の文言を変更する。同じPRのhead branch上で修正し、新しいPRは作成しない。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | README.mdの`PR fix workflow V1 test - before review`を`PR fix workflow V1 test - fixed`に変更する | README.mdの最終行が`PR fix workflow V1 test - fixed`で、旧文言がREADME内に残らない |
| R2 | 元PRの目的・他の内容を変えない | README.mdの差分は該当1行の置換のみ（+1/-1）。改行はCRLFのまま |
| R3 | 既存機能を変更しない | README.md以外のアプリケーションコードに差分がない。既存テストが成功する |

- 対象範囲：README.mdの1行、本Task文書
- 対象外：Markdown描画（箇条書き記号・空行）の変更、本体機能の変更、`.claude/tasks/issue-12.md`の変更、review threadのresolve、mainの最新化（merge/rebase）
- 互換性・データ移行：なし

## 禁止事項

- 新しいPull Requestの作成、mainへの直接push、Pull Requestのmerge、deploy / release公開、Issueの手動close。
- 対象PRのhead branch以外へのpush、review threadの自動resolve、branch protectionの回避。
- ダミー変更・空commitによるCI再実行、CIやテストの検証条件の弱体化。
- 修正対象に含まれない機能追加・リファクタリング、秘密情報の記載。

## 検証計画

- 実行する確認：`python -m unittest discover -s tests`（Local runtime記録）、`git diff` / `git diff --cached` / `git diff --check`、README.mdの改行・最終行の確認（R1・R2）、push後のGitHub Actions（Python 3.12）の結果
- 実接続・データ変更などの副作用：なし
- 最終報告：`/fix`の最終報告項目に従う。

## 完了条件

- [ ] F1が解消され、上記受入条件を満たす。
- [ ] 既存テストが成功している。最終変更に対応する結果を記録する。
- [ ] security / reviewの未解決Critical / Highが0件。
- [ ] releaseが最終差分・検証結果・PR本文の更新内容を確認している。
- [ ] head branchへのpush後、CIの完了を確認し、既存PR #13の本文へ最新結果を反映する。
- 案件固有の追加条件：なし。

## Workflow

`research → implementation → test → security → review → release`

Critical / High、Fix target未解消、テスト失敗があれば該当工程へ戻し、修正後はtest → security → reviewを経てreleaseへ進む。
