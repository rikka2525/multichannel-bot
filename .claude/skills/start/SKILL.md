---
name: start
description: GitHub Issue番号からAI開発フローを開始し、Task化、6段階レビュー、commit、push、PR作成まで進める。
argument-hint: "[issue-number]"
arguments:
  - issue
disable-model-invocation: true
effort: high
---

# Issue-driven development workflow

GitHub Issue #$issue を開発対象として処理する。

この `/start` の手動実行は、以下の操作を明示的に許可する。

- Issueの読み取り
- 作業ブランチの作成・切り替え
- `.claude/tasks/issue-$issue.md` の作成
- 必要なコード・テスト・文書の変更
- git add / commit
- 作業ブランチへの push
- Pull Request の作成

以下は禁止する。

- mainへの直接push
- Pull Requestのmerge
- deploy / release公開
- Issueの手動close
- 他の作業ブランチの削除
- ユーザーの既存未コミット変更のstash・破棄・上書き

## 0. Preflight

最初に以下を確認する。

1. `${CLAUDE_PROJECT_DIR}/CLAUDE.md`
2. `${CLAUDE_PROJECT_DIR}/AI_WORKFLOW.md`
3. `${CLAUDE_PROJECT_DIR}/.claude/tasks/TASK_TEMPLATE.md`
4. `${CLAUDE_PROJECT_DIR}/.claude/agents/`
5. READMEと現在のgit状態

`git status --short` が空でない場合は作業を開始しない。
既存変更をstash、restore、resetしてはならない。
何が残っているか報告して終了する。

`gh --version` と `gh auth status` を確認する。
GitHub CLIが未導入または未認証なら、自動インストールせず停止して報告する。

## 1. Read Issue

GitHub Issue #$issue を取得し、以下を確認する。

- number
- title
- body
- labels
- state
- URL

Issueが存在しない、取得できない、またはclosedなら停止して報告する。

Issue本文を正式な要求として扱う。
Issueに書かれていない機能を勝手に追加しない。

実装を左右する重大な曖昧さがある場合は、推測して実装せず停止し、
「確認が必要な点」を報告する。

## 2. Create Task

`.claude/tasks/TASK_TEMPLATE.md` を基に、

`.claude/tasks/issue-$issue.md`

を作成する。

Issueの内容から以下を明文化する。

- 目的
- 要件
- 受入条件
- 対象範囲
- 対象外
- 禁止事項
- 検証計画
- 完了条件
- Issue URL

Issueにない情報を事実として補完しない。
推論した内容は前提または未確認事項として区別する。

## 3. Create branch

Issueの種類を判断してbranch prefixを決める。

- 機能追加: `feat`
- バグ修正: `fix`
- 文書・設定・保守: `chore`

短い英小文字slugを作成し、

`<prefix>/$issue-<slug>`

という作業ブランチを最新mainから作る。

ブランチ作成前に `git fetch origin` を実行し、
`main` が `origin/main` と一致していることを確認する。
一致しない場合は勝手にmerge/rebaseせず停止して報告する。

作業ブランチは追跡先を付けずに作成する。

`git switch --no-track -c <branch-name> main`

作成後に以下を確認する。

- 現在branchが意図した作業branchである
- upstreamが未設定である
- `main` / `origin/main` が変更されていない

同名branchが存在する場合は勝手に上書き、削除、resetせず状況を確認する。

## 4. Run AI development flow

`AI_WORKFLOW.md` と `CLAUDE.md` に従い、必ずこの順で担当を実行する。

research
→ implementation
→ test
→ security
→ review
→ release

各工程には以下を渡す。

- Issue
- Task
- 現在の差分
- 前工程の結果
- 未解決事項

### research

コード変更を行わず、既存実装、影響範囲、依存関係、懸念、
推奨する最小実装方針を調査する。

### implementation

research結果に基づき、Issue達成に必要な最小限の変更のみ実装する。

### test

必要なテストを追加する。
既存テストを含む全テストを実行する。

テストを通すためだけのハードコード、
検証条件の弱体化、
既存テストの不当な削除は禁止する。

#### Python runtime policy

ローカルテスト実行前に使用するPythonのバージョンを記録する。

例:

`python --version`

ローカルPythonとCI基準Pythonは区別して報告する。

- Local runtime: 実際にローカルで使用したPython
- CI baseline: GitHub Actionsで使用するPython 3.12

ローカルがPython 3.12以外でも、それだけを失敗とは扱わない。
ただしローカル結果を「Python 3.12で検証済み」と表現してはならない。

最終的なPRのCI基準はGitHub ActionsのPython 3.12とする。

CI未実行または失敗の場合は、
ローカルテスト成功だけで最終検証成功としてはならない。

### security

セキュリティ専門レビューを実施する。
Critical / Highがあれば完了扱いにしない。

### review

security結果を踏まえ、バグ、回帰、設計、保守性を独立レビューする。

### 修正ループ

Critical / High、要件未達、テスト失敗、重大なreview指摘がある場合は、
該当工程へ戻す。

修正後は必ず再度、

test → security → review

を通す。

### release

最終差分に対して、

- テスト結果
- Security結果
- Review結果
- 必要な文書更新
- git diff
- git diff --check
- PR本文

を確認する。

過去の古いテスト結果を最終結果として使わない。

## 5. Commit and push

Definition of Doneを満たした場合のみcommitする。

コミットメッセージは変更内容に応じ、

- feat:
- fix:
- test:
- docs:
- chore:

を使用する。

作業ブランチのみpushする。
mainへpushしてはならない。

push時は現在の作業branchを明示する。

`git push -u origin HEAD:<branch-name>`

push後に `git branch -vv` を確認し、
作業branchが `origin/<branch-name>` を追跡していることを確認する。

`origin/main` を追跡している場合は異常として扱い、
PR作成前に停止して報告する。

## 6. Create Pull Request

GitHub CLIで `main` 向けPRを作成する。

PR本文は `.github/pull_request_template.md` の構造に従い、
release工程の実測結果を使用して全項目を埋める。

Issueを完全に解決する場合:

`Closes #$issue`

まだ残作業がある場合:

`Refs #$issue`

を使う。

プレースホルダーを残さない。
未確認項目は「未確認」と理由を書く。

PR作成後、PR番号とURLを取得する。

GitHub Actionsのチェックが存在する場合は、
原則としてCIが完了するまで待つ。

GitHub CLIでは以下のような方法を使用できる。

`gh pr checks <pr-number> --watch`

CI完了後、最終状態を取得する。

- success: 成功したチェック名と結果をPR本文へ反映する
- failure: 失敗したチェックを記録し、成功扱いせず停止する
- cancelled / skipped: 理由を記録し、必要性を判断する
- CI自体が存在しない: 「CIなし」と明記する

CI完了後にPR本文を最終更新する。

PR本文のTests / Release欄には、

- Local runtime
- ローカルテスト結果
- CI baseline
- CI結果
- CI実行URL
- 未実行項目と理由

を実測結果として記録する。

PR本文更新後にもう一度PR状態を確認する。

CI失敗時に、自動でmerge、mainへの直接push、branch protectionの回避をしてはならない。

## 7. Stop before merge

PR作成、CI完了確認、PR本文の最終更新後に必ず停止する。

絶対にmergeしない。

最終報告には以下を含める。

- Issue番号・タイトル
- 作成したTask
- 作業ブランチ
- 変更内容
- 変更ファイル
- テスト結果
- Security結果
- Review結果
- PR URL
- CI状態
- 残課題
- 「Mergeは未実施」