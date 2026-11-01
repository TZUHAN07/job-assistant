# 登入 MVP：本機設定與驗證

履歷、職缺、匹配、求職信、求職追蹤與面試 API 已接入登入身分與資料歸屬檢查。靜態頁面、Swagger 及 health 仍可公開開啟；頁面讀取私人資料時需要登入。

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
- 註冊、登入、登出與所有資料異動 API 必須帶設定相符的 Origin；缺少或不符會回 403。命令列客戶端也需要此標頭。SameSite 是額外防護，並非唯一檢查。
- JWT 的 sid 對應 auth_sessions。每次身分查詢都確認帳號啟用、session 未過期且未撤銷。
- 登出只撤銷目前 session；其他裝置登入不受影響。過期需重新登入，目前沒有 refresh token。
- 登入交易成功後才發 Cookie；登出交易成功後才清除 Cookie。
- 不會把第一個註冊者指定為舊資料的擁有者；user_id=1 的資料歸屬留待後續明確設定。
- 資料 API 的 `user_id` 來自驗證後的帳號，不能由前端指定。未登入回 401；資料不存在或不屬於本人都回 404。
- 匹配同時檢查其履歷與職缺的歸屬；求職信、追蹤、題組也檢查關聯資料。列表先在 SQL 限制本人，再分頁／計數。
- 成功的私人資料回應設為 `Cache-Control: no-store`。
- 本次沒有新增資料表或變更欄位，不需新增 Alembic migration。刪除關聯的 ORM 設定改為交由既有 FK CASCADE 處理。
- 清理過期 session、忘記密碼、Email 驗證及登入頁面尚未實作。

## 測試

```bash
.venv/bin/python -m pytest tests/test_auth_login.py tests/test_auth_api.py tests/test_interview_api.py tests/test_interview_usage.py tests/test_data_access.py tests/integration/test_applications.py -q
```

使用隔離測試資料庫；不呼叫真實 Gemini。包含 JWT 過期、簽章錯誤、session 過期／撤銷、帳號停用、來源檢查、交易失敗及 migration 升降版。


## 手動驗證資料歸屬

1. 先登出，呼叫 `GET /resumes` 應回 401。
2. 登入帳號 A，確認 `/auth/me`；新帳號的履歷與職缺列表可能是空的，舊 user_id=1 資料仍保留但不可見。
3. 使用 A 上傳測試履歷、建立職缺與匹配，記下各 ID。這些生成步驟會呼叫外部服務；自動測試已用替身涵蓋，非每次都要手動重跑。
4. 登出並登入帳號 B；列表不應出現 A 的資料。用 A 的 matching ID 查詢 `/matchings/{id}` 應回 404。
5. B 嘗試用 A 的履歷／職缺 ID 建立匹配、用 A 的 matching ID 生成求職信／題組，應回 404 且不呼叫 AI。
6. 切回 A，原資料仍可正常讀取。登出後再查詢私人資料應回 401。

目前沒有登入頁面；請先在同一個 `127.0.0.1:8000` 的 Swagger 登入，再操作應用頁面。Cookie 過期後需重新登入，不會退回 user_id=1。

理解順序：`auth_service.get_current_user_id` 辨識「你是誰」→ router 用 `data_access` 條件限制「你能操作哪筆」→ 新增資料明確寫入登入者的 user_id。ORM 的舊 default=1 暫時保留給既有本機資料流程；HTTP API 不依賴它，不代表所有離線腳本都具備身分驗證。
