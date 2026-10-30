# 登入 MVP：本機設定與驗證

這一階段只保護 `/auth/me` 與 `/auth/logout`。履歷、職缺、匹配、求職信、追蹤及面試 API 尚未統一接入身分驗證，不可當成已完成多使用者隔離。

## 本機設定

1. 在專案虛擬環境安裝 requirements.txt。
2. 執行 `.venv/bin/alembic upgrade head`，新增 auth_sessions 表。
3. 在本機 `.env` 設定以下三項（不要把真實金鑰提交或貼到聊天中）：

```dotenv
AUTH_JWT_SECRET=自行產生的隨機金鑰
AUTH_ORIGIN=http://127.0.0.1:8000
AUTH_COOKIE_SECURE=false
```

產生金鑰：`.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"`。將結果填入 AUTH_JWT_SECRET；每次重新產生會讓舊 JWT 驗證失敗。不要使用短密碼作為金鑰。

正式 HTTPS 環境必須使用 `AUTH_COOKIE_SECURE=true` 並設定確切的 HTTPS origin。未設定 Cookie 選項時預設 true。本機請統一使用 127.0.0.1，不要混用 localhost，否則 origin 與 Cookie 不一致。

修改 `.env` 後手動重啟 Uvicorn，reload 不保證監看環境檔案。

## Swagger 操作

使用 `http://127.0.0.1:8000/docs`，不必點 Authorize，也不必手動複製 JWT。

1. `GET /auth/me`：尚未登入回 401。
2. `POST /auth/login`：傳入已註冊的 email、password，成功回 200，瀏覽器自動保存 HttpOnly Cookie。回應 JSON 不包含 JWT。
3. `GET /auth/me`：回 200，顯示自己的帳號資訊。
4. `POST /auth/logout`：回 200，撤銷本次登入並清除 Cookie。
5. 再次 `GET /auth/me`：回 401。
6. 使用錯誤密碼登入：回 401。不存在或停用的帳號使用相同提示。

登入／註冊目前每個來源 IP 限制 5 次／分鐘，過量回 429。自動測試會關閉 limiter。

## 流程與限制

- JWT 使用 HS256，固定驗證算法、issuer、audience、必要欄位及 30 分鐘期限。
- Cookie：HttpOnly、SameSite=Lax、Path=/，正式環境 Secure。
- 註冊、登入、登出必須帶設定相符的 Origin；缺少或不符會回 403。命令列客戶端也需要此標頭。SameSite 是額外防護，並非唯一檢查。
- JWT 的 sid 對應 auth_sessions。每次身分查詢都確認帳號啟用、session 未過期且未撤銷。
- 登出只撤銷目前 session；其他裝置登入不受影響。過期需重新登入，目前沒有 refresh token。
- 登入交易成功後才發 Cookie；登出交易成功後才清除 Cookie。
- 不會把第一個註冊者指定為舊資料的擁有者；user_id=1 的資料歸屬留待後續明確設定。
- 後續所有使用 Cookie 的資料異動 API，也必須接入來源檢查與資料擁有者驗證。
- 清理過期 session、忘記密碼、Email 驗證及登入頁面尚未實作。

## 測試

```bash
.venv/bin/python -m pytest tests/test_auth_login.py tests/test_auth_api.py tests/test_interview_api.py tests/test_interview_usage.py -q
```

使用隔離測試資料庫；不呼叫真實 Gemini。包含 JWT 過期、簽章錯誤、session 過期／撤銷、帳號停用、來源檢查、交易失敗及 migration 升降版。
