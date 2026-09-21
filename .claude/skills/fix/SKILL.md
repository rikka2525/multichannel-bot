---
name: fix
description: 既存Pull Requestのレビュー指摘、CI失敗、Remaining concernsを取得し、同じPRブランチ上で必要最小限の修正、再検証、push、CI確認まで行う。
argument-hint: "[pr-number]"
arguments:
  - pr
disable-model-invocation: true
effort: high
---

# Pull Request fix workflow

GitHub Pull Request #$pr を修正対象として処理する。

この `/fix` の手動実行は、以下の操作を明示的に許可する。

- Pull Requestの読み取り
- Review / review comments / CI状態の読み取り
- PR本文のRemaining concernsの読み取り
- 対象PRのhead branchへの切り替え
- `.claude/tasks/fix-pr-$pr.md` の作成
- 修正に必要なコード・テスト・文書の変更
- git add / commit
- 対象PRのhead branchへのpush
- GitHub Actionsの完了確認
- 対象PR本文の検証結果更新

以下は禁止する。

- 新しいPull Requestの作成
- mainへの直接push
- Pull Requestのmerge
- deploy / release公開
- Issueの手動close
- Review thread / review commentの自動resolve
- 対象PR以外のbranchへのpush
- 他の作業branchの削除
- branch protectionの回避
- ユーザーの既存未コミット変更のstash・破棄・上書き
- 修正対象に含まれない機能追加
- CIを通すためだけの検証条件の弱体化
- ダミー変更・空commitによるCIの再実行

## 0. Preflight

最初に以下を確認する。

1. `${CLAUDE_PROJECT_DIR}/CLAUDE.md`
2. `${CLAUDE_PROJECT_DIR}/AI_WORKFLOW.md`
3. `${CLAUDE_PROJECT_DIR}/.claude/tasks/TASK_TEMPLATE.md`
4. `${CLAUDE_PROJECT_DIR}/.claude/agents/`
5. README
6. 現在のgit状態

`git status --short` が空でない場合は作業を開始しない。

既存変更をstash、restore、resetしてはならない。
何が残っているか報告して終了する。

`gh --version` と `gh auth status` を確認する。

GitHub CLIが未導入または未認証なら、
自動インストールせず停止して報告する。

`git fetch origin` を実行する。

この時点ではbranch切り替え、merge、rebase、resetを行わない。

## 1. Read Pull Request

GitHub Pull Request #$pr を取得し、以下を確認する。

- number
- title
- body
- state
- URL
- base branch
- head branch
- head SHA
- head repository
- author
- merge状態
- draft状態
- CI / status checks
- linked Issue

PRが存在しない、取得できない場合は停止する。

PRがclosedまたはmergedの場合は停止する。

V1では `base branch` が `main` 以外の場合は停止して報告する。

V1では対象PRのhead branchが現在のrepository内に存在する場合のみ処理する。

fork由来など、別repositoryへのpushが必要なPRでは停止して報告する。

この時点ではまだコードを変更しない。

## 2. Collect fix targets

修正対象を以下の3種類から取得する。

### A. Review feedback

以下を取得する。

- Pull Request reviews
- inline review comments
- review threads
- change requestedの内容
- 通常のPR conversationで明示された修正要求

明示的にresolved済みと確認できるreview threadは対象外にできる。

resolved状態を確認できない場合は、
勝手に「解決済み」と判断しない。

その場合は「状態未確認のreview input」として記録する。

単なる感想、質問、承認コメントを修正要求として扱わない。

### B. CI failures

現在のPRに紐づくstatus checksを取得する。

失敗しているcheckがある場合は、

- check名
- workflow名
- job名
- failure状態
- 実行URL
- failure logの関連部分

を確認する。

ログ全体を無差別に修正理由として扱わず、
実際のfailure原因を特定する。

CIが一時的な外部障害やGitHub側障害などで、
コード変更による修正が不要と判断される場合は、
ダミー変更や空commitを作成せず停止して報告する。

### C. Remaining concerns

PR本文の `Remaining concerns` を確認する。

未解決として明示されている項目のうち、
コード・テスト・文書変更によって解消可能なものを修正候補とする。

「人間が判断する」と明示された事項は、
勝手に実装判断してはならない。

### Fix target selection

取得した各候補を、

- 必須修正
- 修正候補
- 人間判断
- 対象外

に分類する。

修正対象には一意なIDを付ける。

例:

- F1: Review comment
- F2: CI failure
- F3: Remaining concern

各項目について以下を記録する。

- source
- 内容
- 根拠
- 影響範囲
- 修正方法
- 検証方法
- status

修正対象が1件も存在しない場合は何も変更しない。

その場合は、

「修正対象が見つかりませんでした。
変更・commit・pushは行っていません。」

と報告して終了する。

曖昧なreviewコメントを勝手に解釈してコード変更してはならない。

実装を左右する重大な曖昧さがある場合は停止し、
確認が必要な点を報告する。

## 3. Create fix Task

`.claude/tasks/TASK_TEMPLATE.md` を参考に、

`.claude/tasks/fix-pr-$pr.md`

を作成する。

Taskには以下を含める。

- PR番号
- PRタイトル
- PR URL
- base branch
- head branch
- head SHA
- linked Issue
- 修正対象一覧
- 各Fix targetのsource
- 目的
- 要件
- 受入条件
- 対象範囲
- 対象外
- 禁止事項
- 検証計画
- 完了条件

特に修正対象は表形式などで、

| ID | Source | 内容 | 修正方針 | 検証方法 | Status |
| --- | --- | --- | --- | --- | --- |

として追跡できる状態にする。

PRやreviewに書かれていない情報を、
事実として補完してはならない。

## 4. Checkout PR branch safely

PRのhead branchを `<head-branch>` とする。

まずremote branchの存在を確認する。

`origin/<head-branch>` が存在しない場合は停止する。

ローカルに同名branchが存在しない場合は、

`git switch --track -c <head-branch> origin/<head-branch>`

で作成する。

ローカルに同名branchが既に存在する場合は、
勝手に削除、reset、上書きしない。

以下を比較する。

- local HEAD
- origin/<head-branch>
- PR head SHA

ローカルbranchがremoteとdivergeしている場合は停止して報告する。

PR head SHAと `origin/<head-branch>` が一致しない場合も停止する。

branch切り替え後に以下を確認する。

- 現在branchがPRのhead branchである
- upstreamが `origin/<head-branch>` である
- HEADがPR head SHAと一致する
- `main` / `origin/main` が変更されていない
- working treeがcleanである

upstreamが `origin/main` または別branchになっている場合は、
勝手にpushせず停止して報告する。

PR branchを最新mainへ自動merge / rebaseしてはならない。

必要な場合は人間の判断を求める。

## 5. Run AI fix flow

`AI_WORKFLOW.md` と `CLAUDE.md` に従い、
以下の順で担当を実行する。

research
→ implementation
→ test
→ security
→ review
→ release

各工程には以下を渡す。

- PR
- Fix Task
- Fix target一覧
- review feedback
- CI failure情報
- Remaining concerns
- 現在の差分
- 前工程の結果
- 未解決事項

### research

コード変更を行わず、

- 指摘の再現性
- failure原因
- 関連コード
- 影響範囲
- 回帰リスク
- 最小修正方針

を調査する。

reviewコメントに書かれている修正方法を
盲目的に実装せず、問題の根本原因を確認する。

### implementation

research結果に基づき、
Fix targetを解消するための必要最小限の変更のみ実装する。

対象外のリファクタリングや機能追加を混ぜない。

元PRの目的を変更してはならない。

### test

修正に必要なテストを追加または更新する。

既存テストを含む必要な検証を実行する。

Fix targetごとに、
どのテストまたは確認で解消を検証したか記録する。

テストを通すためだけの、

- ハードコード
- assertion削除
- 検証条件の弱体化
- failing testの不当な削除
- test skip追加

は禁止する。

#### Python runtime policy

ローカルテスト実行前に使用するPythonのバージョンを記録する。

例:

`python --version`

ローカルPythonとCI基準Pythonを区別して報告する。

- Local runtime: 実際にローカルで使用したPython
- CI baseline: GitHub Actionsで使用するPython 3.12

ローカルがPython 3.12以外でも、
それだけを失敗とは扱わない。

ただしローカル結果を
「Python 3.12で検証済み」と表現してはならない。

最終的なCI基準はGitHub ActionsのPython 3.12とする。

### security

最終修正差分に対して
セキュリティ専門レビューを実施する。

Critical / Highがあれば完了扱いにしない。

元PRに存在しなかった新しいsecurity issueを
修正によって導入していないか確認する。

### review

implementation担当とは独立したreviewを実施する。

特に以下を確認する。

- Fix targetが実際に解消されている
- 元PRの要件を壊していない
- 新しい回帰を導入していない
- 修正範囲が過剰でない
- テストが十分である
- security結果
- 最終diff

### 修正ループ

以下が存在する場合は該当工程へ戻る。

- Critical / High
- Fix target未解消
- テスト失敗
- CI原因の未解決
- 要件未達
- 重大なreview指摘
- 回帰

修正後は必ず再度、

test → security → review

を通す。

### release

最終差分について以下を確認する。

- 全Fix targetのstatus
- テスト結果
- Security結果
- Review結果
- 必要な文書更新
- `git status`
- `git diff`
- `git diff --cached`
- `git diff --check`
- 変更ファイル一覧
- PR本文
- 未解決review feedback

過去の古いテスト結果を
最終結果として使わない。

## 6. Commit and push

Definition of Doneを満たした場合のみcommitする。

commit対象が存在しない場合は、
空commitを作成しない。

コミットメッセージは変更内容に応じて、

- fix:
- test:
- docs:
- chore:

などを使用する。

commit前に、
対象PRのhead branch上にいることを再確認する。

push先は対象PRのhead branchのみとする。

`git push origin HEAD:<head-branch>`

push後に `git branch -vv` を確認する。

以下を満たすことを確認する。

- 現在branchが `<head-branch>`
- upstreamが `origin/<head-branch>`
- `origin/main` を追跡していない
- mainへpushしていない

条件を満たさない場合は停止して報告する。

新しいPRを作成してはならない。

## 7. Wait for CI

push後、既存PR #$pr の最新head SHAを再取得する。

自分がpushしたcommit SHAと一致することを確認する。

一致しない場合は、
他者による同時更新の可能性があるため停止する。

GitHub Actionsのチェックが存在する場合は、
原則としてCI完了まで待つ。

例:

`gh pr checks $pr --watch`

CI完了後に最終状態を取得する。

- success: 成功したcheckと結果を記録する
- failure: failure内容を取得し、成功扱いしない
- cancelled: 理由を記録する
- skipped: 必要性を確認する
- CIなし: 「CIなし」と明記する

CIが失敗した場合は、
failureが今回の修正に起因するかを調査する。

修正可能かつFix scope内であれば、
implementation工程へ戻る。

修正範囲外、外部障害、重大な曖昧さがある場合は停止する。

CI失敗時に、

- merge
- mainへの直接push
- branch protection回避
- ダミーcommit
- 検証条件の弱体化

を行ってはならない。

## 8. Update existing Pull Request

新しいPRは作成しない。

対象PR #$pr を更新する。

PR本文を更新する前に、
最新のPR本文を再取得する。

人間が追加した説明やコメントを
勝手に削除・上書きしてはならない。

PR本文が `.github/pull_request_template.md` の構造を使用している場合は、
原則として以下の検証系セクションのみを最新実測値へ更新する。

- Tests
- Security
- Review
- Remaining concerns
- Release

Summaryなど、
元PRの目的を示す内容は不要に書き換えない。

PR本文を安全に部分更新できない場合は、
既存本文を破壊せず、
最終検証結果をPR commentとして追記する。

Tests / Releaseには以下を記録する。

- Fix target一覧と結果
- Local runtime
- ローカルテスト結果
- CI baseline
- CI結果
- CI実行URL
- 変更ファイル
- 未実行項目と理由
- 残課題

Review欄には、

- 解消したreview指摘
- 未解消review指摘
- 新しく見つかった指摘

を区別して記録する。

review threadやreview commentを
自動でresolveしてはならない。

「修正済み」と「GitHub上でresolved」は別状態として扱う。

PR本文更新後に、
もう一度PR状態と最新head SHAを確認する。

## 9. Stop before merge

CI完了確認とPR情報更新後に必ず停止する。

絶対にmergeしない。

Review threadを自動resolveしない。

Issueを自動closeしない。

deployしない。

最終報告には以下を含める。

- PR番号・タイトル
- PR URL
- linked Issue
- 作業branch
- 修正Task
- Fix target一覧
- 解消した項目
- 未解消項目
- 変更内容
- 変更ファイル
- commit SHA
- Local runtime
- ローカルテスト結果
- Security結果
- Review結果
- CI状態
- CI URL
- review threadの状態
- 残課題
- 「新しいPRは作成していない」
- 「Mergeは未実施」