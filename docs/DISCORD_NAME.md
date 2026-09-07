# Discord表示名の統一

2026-09-08、ユーザーによる設定変更後、Discord公式APIでBotユーザー名と実返信の投稿者名が`MultiChannel Bot`であることを確認しました。サーバーニックネームは未設定です。コードは表示名を上書きしていません。以下は設定手順です。

1. [Discord Developer Portal](https://discord.com/developers/applications)で、今回の実接続に使ったアプリを選択。
2. General InformationのNAME（アプリ名）を`MultiChannel Bot`へ変更して保存。
3. BotページのUSERNAMEを`MultiChannel Bot`へ変更して保存。トークン再発行は不要です。
4. テストサーバーのメンバー一覧でBotを右クリックし、ニックネーム変更が利用できる場合は`MultiChannel Bot`へ設定するか、既存ニックネームを解除。権限がない場合はサーバー管理者に変更を依頼。
5. Botのプロフィールと、サーバー内の投稿者表示が`MultiChannel Bot`になったことを確認。

アプリ名とBotユーザー名は別設定で、サーバーニックネームによって表示が上書きされます。認証済みBotで変更が制限される場合は公式案内のサポート手順を使用してください。

根拠（2026-09-07確認）：[Discord公式：Bot名の変更](https://support-dev.discord.com/hc/en-us/articles/6129090215959-How-Do-I-Change-My-Bot-s-Name)、[サーバーニックネーム](https://support.discord.com/hc/en-us/articles/219070107-Server-Nicknames)。
