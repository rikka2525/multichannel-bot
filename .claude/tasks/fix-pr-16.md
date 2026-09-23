# Task: PR #16 修正（DBサイドカーファイルへの出力拒否）

手順は[AI_WORKFLOW.md](../../AI_WORKFLOW.md)、共通ルールは[CLAUDE.md](../../CLAUDE.md)、担当の詳細は[agents](../agents/)を参照する。

## 基本情報

- PR：#16 「feat: アンケート回答を安全にCSVエクスポートするローカルCLIを追加」
- PR URL：https://github.com/rikka2525/multichannel-bot/pull/16
- base branch：`main`
- head branch：`feat/14-feedback-csv-export`
- head SHA（修正開始時）：`61bf8536b72cdefd70e20037c0c6e4add90526ea`
- linked Issue：#14（https://github.com/rikka2525/multichannel-bot/issues/14）
- 元タスク仕様：[issue-14.md](issue-14.md)
- 対象環境・前提：ローカル環境のみ。CI基準はGitHub ActionsのPython 3.12。
- 未確認事項：なし

## 修正対象の収集結果

- Review（PR reviews）：0件。inline review comment：0件。review thread：0件。
- PR conversation：オーナーによる修正要求1件（2026-09-23、https://github.com/rikka2525/multichannel-bot/pull/16#issuecomment-5792434446）。
- CI：`Tests / Python 3.12 unit tests` は SUCCESS。失敗なし。
- Remaining concerns：Low 5件・Info 3件。うち「`--force`でDBサイドカーを上書き可能」はPRコメントの要求と同一のためF1に統合する。

## 修正対象一覧

| ID | Source | 内容 | 修正方針 | 検証方法 | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | PR conversation（オーナーコメント）＋ Remaining concerns「`--force`でDBサイドカー上書き可能」 | `--force`指定時でも、元DBのサイドカー（`<db>-journal`、`<db>-wal`、`<db>-shm`）を出力先に指定できないようにする。このケースの自動テストを追加する | `export_feedback`でDB本体との同一判定に加え、3種のサイドカーパスとの同一判定で拒否する（固定エラーメッセージ・終了コード1） | 3種それぞれについて`--force`あり・なしで終了コード1、既存サイドカー・DBの内容が不変、エラーに本文を含まないことを自動テストで確認。全テスト・Security・Review・CIを再実行 | 修正済み（ローカル検証済み・CI未確認）。最終状態は「修正結果」参照 |

### 分類（F1以外のRemaining concerns）

| 項目 | 分類 | 理由 |
| --- | --- | --- |
| Low-1：存在確認と`os.replace`間のTOCTOU | 人間判断 | PRで「必要時に検討」として意図的に見送った。今回の修正要求に含まれない |
| Low-2：出力先シンボリックリンクの追従 | 人間判断 | 同上 |
| Low-3：類似文字・ゼロ幅文字による数式対策の回避 | 人間判断 | 同上。実表計算ソフトでの挙動未検証 |
| Low：cp932端末で成功メッセージ表示時の`UnicodeEncodeError` | 人間判断 | 同上 |
| Info 3件（一時ファイル残存、`exports/`外のCSV、WAL/メモリ/UNC） | 対象外 | 運用上の注意・現行運用で影響なしと記録済み |
| 表計算ソフトでの実表示確認なし | 人間判断 | 人間による確認事項 |

## 目的

PR #16のCSVエクスポートCLIで、`--force`指定時に元DBのサイドカーファイルを上書きしてDBの整合性（クラッシュリカバリ）を損なう可能性をなくす。

## 要件

| ID | 必須動作・制約 | 受入条件（確認可能な期待結果） |
| --- | --- | --- |
| R1 | 出力先が`<db>-journal`、`<db>-wal`、`<db>-shm`のいずれか | `--force`の有無にかかわらず`Error: ...`を表示し終了コード1。ファイルを書き込まない |
| R2 | 拒否時の副作用 | 既存サイドカー・DB本体の内容が変わらない。一時ファイルが残らない。出力に回答本文を含まない |
| R3 | 回帰 | 既存の全テスト（元PRの118件）が成功し、通常の出力先への出力・`--force`上書きの動作は変わらない |

- 対象範囲：`tools/export_feedback.py`、`tests/test_export_feedback.py`、必要ならREADMEのCSVエクスポート節。
- 対象外：F1以外のRemaining concerns（上表）、新機能、リファクタリング。
- 互換性：通常の出力先の動作は変更しない。

## 禁止事項

- 新しいPR作成、mainへの直接push、merge、deploy、Issueの手動close、review threadの自動resolve、対象PR以外のbranchへのpush。
- 修正対象外の機能追加、検証条件の弱体化、テストのskip追加、ダミー変更・空commit。
- 秘密情報の記載、実DB（`data/`）の変更。

## 完了条件

- [x] F1の受入条件を満たす（ローカルWindows・Python 3.14.6の自動テストで確認。POSIX分岐はCIで確認予定）。
- [ ] 追加テストを含む全テストがローカルで成功し、GitHub Actions（Python 3.12）が成功する（ローカルは成功。CIはpush後に確認・未実行）。
- [x] security / reviewの未解決Critical / Highが0件。
- [ ] releaseが最終差分・検証結果・文書を確認し、PR本文の検証系セクションを更新する。
- [ ] 不要なファイルを残さない。

## Workflow

`research → implementation → test → security → review → release`

## 検証計画

- `python -m unittest discover -s tests -v`（ローカル。Pythonバージョンを記録し、3.12以外なら「3.12で検証済み」と表現しない）。
- GitHub Actions `Tests / Python 3.12 unit tests`。
- 副作用：なし（テストは一時ディレクトリのみ使用）。

## 修正結果（release時点、2026-09-23）

### 修正対象ステータス

| ID | 発見元 | 内容 | 最終状態 | 検証 |
| --- | --- | --- | --- | --- |
| F1 | PR conversation（オーナー） | `--force`でも`<db>-journal`/`-wal`/`-shm`への出力を拒否 | 修正済み | 既存・未作成サイドカー×`--force`有無、DB読込前の拒否、`..`別名、相対パス（subprocess）、別ディレクトリ・類似名は許可 |
| L-1 | security（ループ、parentで再現） | Windowsの末尾ドット・スペース（`test.db-journal.`、`test.db.`）で判定を回避（Mediumに再評価） | 修正済み | 末尾ドット・スペース4パターン×`--force`有無 |
| L-2 | security（ループ、parentで再現） | 拡張長プレフィックス`\\?\`での回避（Low） | 修正済み | サイドカー・DB本体の両方 |
| L-3 | security（ループ、parentで再現） | 8.3短縮名の親＋末尾ドットでの回避（Low） | 修正済み | 短縮名親、`\\?\`＋短縮名、既存サイドカー自体の短縮名 |
| L-4 | security（ループ、Low-A、parentで再現） | `<sidecar>.\x\..`形式（最終要素が`..`）での回避 | 修正済み | 3パターン＋別ディレクトリでは許可されること |
| L-5 | security（ループ） | ADS形式（`::$DATA`、`:s`） | 修正済み（テストを厳格化） | Windowsでサイドカーエラーとして拒否 |
| L-6 | security（ループ、Low-B） | POSIXでバックスラッシュ入りの名前が一時ディレクトリ外へ書き込み得るテスト上の問題 | 修正済み（テスト側） | `enter_sandbox`/`assert_nothing_escaped`で外部への書き込みを検出 |

### 検証結果

- ローカル（release再実行）：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`、Windows 11、Python 3.14.6、最終作業ツリー（HEAD `61bf853`＋未コミット差分）で`Ran 131 tests in 3.759s` / `OK`（終了コード0、実時間約4.2秒、skipなし）。内訳：既存118件＋F1関連13件。
- 各ループでmutation check（修正を外すと該当テストが失敗すること）を実施済み（test報告による）。
- POSIX分岐（`os.name != "nt"`側のアサーション）はローカル未実行。CIで確認する。
- CI（GitHub Actions `Tests / Python 3.12 unit tests`）：push後に確認（未実行）。修正前コミット`61bf853`は成功済み。
- Security（3回目の再監査）：Critical 0 / High 0。ループ中のLow（末尾ドット[Mediumに再評価]、`\\?\`、8.3、Low-A、Low-B、ADS）はすべて解消。
- Review：Approve、Critical 0 / High 0 / Medium 0、任意のLow 4件（下記）。
- `git diff --check`：問題なし。変更ファイルは`README.md`、`tools/export_feedback.py`、`tests/test_export_feedback.py`と本タスクファイル（未追跡）のみ。

### 残課題

| 項目 | 分類 | 理由 |
| --- | --- | --- |
| macOSの大文字小文字を区別しないFSでの名前正規化なし（security Low/Info・review Low 4） | 人間判断 | 本プロジェクトの運用環境はWindows。POSIXでは大小文字を区別する前提。既存サイドカーはsamefileで検出される |
| UNCループバック（`\\localhost\C$\...`）での別名 | 未確認（Info） | ローカルCLIの想定外の指定。未検証 |
| 実際の書き込み先`Path(os.path.abspath(Path(output).resolve()))`も判定対象にする（review Low 1） | 任意・未対応 | 多層防御。現行テストで回避は再現されていない |
| `export_feedback`と`_is_db_sidecar`のパス計算重複・複雑度の増加（review Low 2） | 任意・未対応 | 動作に影響なし。将来の整理候補 |
| POSIX分岐で終了コードを検証していない箇所がある（review Low 3） | 任意・未対応 | テスト強化はtest担当の範囲 |
| TOCTOU（Low-1）、`-mj*`スーパージャーナル、シンボリックリンク・ハードリンクのテスト | 対象外 | F1の要求範囲外。既存の残課題として継続 |
| 旧PRの残課題（Low-2/3、cp932表示、Info） | 対象外 | 「分類」表のとおり |
