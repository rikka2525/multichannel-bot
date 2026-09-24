# Task: READMEにBotが返信しないときのトラブルシューティング節を追加する

手順は[AI_WORKFLOW.md](../../AI_WORKFLOW.md)、共通ルールは[CLAUDE.md](../../CLAUDE.md)、担当の詳細は[agents](../agents/)を参照する。

## 基本情報

- 関連Issue / 資料：https://github.com/rikka2525/multichannel-bot/issues/21 （親Issue：https://github.com/rikka2525/multichannel-bot/issues/20 ）。実装仕様はIssue #21本文と、Issue #21のコメント「Human decisions for implementation」（2026-09-24、rikka2525）。
- 作業ブランチ：`chore/21-readme-troubleshooting`
- 対象環境・前提：文書のみの変更。README既存の前提（Windows / PowerShell、Python 3.12）に合わせる。CI基準はGitHub ActionsのPython 3.12。
- 未確認事項：
  - Discord / Telegramのエラー出力先が標準エラーかどうか（Issue Risksに記載。「コンソールに表示される」という書き方にとどめる）。
- AC6と本Taskの扱い（2026-09-25 ユーザー確認済み）：本Task（`.claude/tasks/issue-21.md`）は従来どおりPRに含めてcommitする。AC6は「成果物として変更する文書・コードは`README.md`のみ」と解釈し、PRにその旨を明記する。

## Human decisions（Issue #21コメントより）

1. `## セットアップ`と`## プライバシー方針`の間に、独立した`## トラブルシューティング`として追加する。
2. 「ログを確認」は「起動したコンソールの出力を確認する」と記載する。ファイルログ機能は追加しない。
3. 対象はDiscord / Telegram。WhatsAppは含めない。
4. Mockは対象に含めない。
5. コンソール表示は固定の文言をそのまま引用せず、意味が分かる説明にする。
6. 文書変更のみだが、既存のunit testを回帰確認として実行する。
7. `docs/`配下およびCHANGELOGは変更しない。
8. 子Issue #21を実装対象として進める。

## 目的

初めてセットアップする利用者が、Botを起動しても返信がないときに確認すべき基本項目を、既存のセットアップ手順・実際の動作と矛盾しない形で`README.md`から確認できるようにする。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | 見出しの追加（AC1、HD1） | `## セットアップ`と`## プライバシー方針`の間に`## トラブルシューティング`が1つあり、既存見出しと名前が重ならない |
| R2 | 6項目の記載（AC2） | 1.プロセスの起動、2.環境変数、3.サービス側の状態、4.権限、5.コンソールのエラー、6.解決しない場合のコンソール出力確認、がそれぞれ確認できる |
| R3 | 正常動作としての無視 | 許可外ユーザー・チャンネル・グループの投稿とBot自身の投稿は表示なしで無視される旨が、既存Discord節・Telegram節と同じ内容で書かれている |
| R4 | 対象サービス（HD3、HD4） | Discord / Telegramのみ。WhatsApp・Mockの項目を含めない |
| R5 | コンソール表示（HD5） | 固定文言を引用せず意味で説明する。記載した変数名・挙動がコード・`.env.example`と一致する |
| R6 | ログ確認（HD2） | 確認先は起動したコンソールの出力。存在しないログファイル・設定を案内しない |
| R7 | 秘密情報（AC3） | 実際のトークン・APIキー・ユーザーID・チャンネルID・チャット本文・個人のパスを例に使わない。ログ等を共有する場合は秘密値・IDを伏せるよう書く。アクセス制限を緩める回避策を書かない |
| R8 | 整合性（AC4） | 既存のセットアップ手順、プライバシー方針、制約、`.env.example`と矛盾しない |
| R9 | 既存表示の保持（AC5） | 既存見出しの階層・順序、CSVエクスポート節へのアンカーリンク、表・mermaid・コードブロックが変更前と同じ |
| R10 | 変更範囲（AC6、HD7） | `git diff --stat`で成果物の変更が`README.md`だけ（本Taskファイルを除く。基本情報を参照） |

- 対象範囲：`README.md`へのトラブルシューティング節の追加。
- 対象外：Bot本体のコード変更、新しいログ機能、設定ファイル（`.env.example`を含む）の仕様変更、Adapterの挙動変更、デプロイ手順の変更、新機能、`docs/`配下・CHANGELOGの変更、WhatsApp・Mockのトラブルシューティング。
- 互換性・データ移行：なし（文書のみ）。

## 禁止事項

- 不要な大規模リファクタリング、不要な依存関係の追加、既存機能を壊す変更。
- 秘密情報の記載、テスト失敗の無視、テストを通すだけのハードコードや検証条件の弱体化。
- ユーザーの未コミット変更の取り消し、無断での実DB変更・外部サービスへの送信。
- 本タスクは`/start 21`により、作業ブランチでのgit add / commit、作業ブランチへのpush、PR作成までを許可されている。mainへの直接push、PRのmerge、deploy / release公開、Issueの手動close、他ブランチの削除、人間の最終確認コメント・確認欄の記入は行わない。
- 案件固有の禁止事項：README既存節の書き換え（追加節以外）、ログ・`.env`・スクリーンショットの貼り付けを促す記述、許可IDを空にするなどの回避策の記載。

## 完了条件

- [ ] 上記要件の受入条件を満たす。
- [ ] 既存unit testを回帰確認として実行し、全件成功している（HD6）。最終変更に対応する結果を記録する。
- [ ] GitHub Actions（Python 3.12）が成功する。
- [ ] security / reviewの未解決Critical / Highが0件。
- [ ] その他の未解決・未確認事項、影響、対応方針を明示する。
- [ ] releaseが必要な文書と最終検証結果を確認し、リリース準備可能と判断する。
- [ ] 全変更ファイル・git diffを確認し、不要なファイルを残さない。
- 案件固有の追加条件・検証の適用除外と理由：記載したコンソール挙動・変数名を`run_bot.py`、`adapters/discord.py`、`adapters/telegram.py`、`config.py`、`.env.example`と照合する。ローカルPythonが3.12以外の場合、ローカル結果を「3.12で検証済み」と表現しない。

## Workflow

`research → implementation → test → security → review → release`

Critical / High、要件未達、テスト失敗があれば完了にせず差し戻す。修正後はtest → security → review → releaseを経て解消を確認する。

## 検証計画・最終報告

- 実行する確認：`python -m unittest discover -s tests -v`（回帰確認）。README追加節の記述をコード・`.env.example`と1項目ずつ照合。見出し一覧・アンカー・相対リンク・コードブロックの対応を差分と構造で確認。`git diff --stat`・`git diff --check`。CIはGitHub Actions `Tests`（Python 3.12）。
- 実接続・データ変更などの副作用と実施条件：なし。Discord / Telegramへの実接続は行わない。
- 最終報告：変更内容・ファイル、実行コマンド・対象状態・結果、未実行と理由、security / review結果、release準備可否、PR URL・CI状態、残課題、「Mergeは未実施」。
