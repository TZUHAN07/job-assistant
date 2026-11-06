# Neon 部署與搬遷

本機 `.env` 的 `DATABASE_URL` 保持本機資料庫。`NEON_DATABASE_URL` 僅供搬遷工具使用，不會自動切換應用程式。

## Render 設定

- `DATABASE_URL`：Neon production 的直接連線 URL，保留 SSL 參數。不要將真實網址提交到 Git。
- 若日後應用程式改用 pooled URL，另設 `DATABASE_MIGRATION_URL` 為直接連線 URL，供 Alembic 使用。
- `AUTH_JWT_SECRET`：獨立且隨機的正式環境密鑰。
- `AUTH_ORIGIN=https://job.tzuhan.dev`
- `AUTH_COOKIE_SECURE=true`

SQLAlchemy 的 asyncpg 連線使用 certifi CA、驗證伺服器憑證及主機名稱。asyncpg 不支援 libpq 的 channel_binding URL 參數，因此不傳入該參數；同步 Alembic/psycopg2 保留它。使用 URL 物件避免密碼中的百分比字元被 ConfigParser 誤解。

## 此次搬遷

已用 pg_dump 一致性快照備份本機，還原到原本空白的 Neon。保留資料、ID、序列與 migration 版本，排除 auth_sessions 的資料，使用者必須重新登入。每張資料表經排序後的 JSON 內容雜湊與筆數均已核對。

完整備份與搬遷檔案位於被 Git 忽略的 scratch/private-backups，內含個人資料與密碼雜湊，勿公開分享。此備份不是定期備份機制。

Render 尚需部署本次程式修改並設定上述環境變數。完成後檢查啟動日誌、登入、本人資料、履歷、求職信與登出；不要用正式資料庫跑 pytest。

搬遷是一次性的快照，不會持續同步本機新增的資料。
