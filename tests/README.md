# 測試

在專案根目錄執行：

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
docker compose -f docker-compose.test.yml -p job-assistant-tests up -d --wait
.venv/bin/python -m pytest -q
```

測試 PostgreSQL 使用本機 5434 port，資料庫名稱為 job_assistant_test。
容器使用 tmpfs，移除或停止後不保留測試資料。每個測試會建立獨立 schema，結束後清除。
若自訂 TEST_DATABASE_URL，必須使用 postgresql+asyncpg 且資料庫名稱以 _test 結尾；帳號需要建立 schema 的權限。
不要使用存有重要資料的資料庫。一般 pytest 不會呼叫 Gemini 或 Firecrawl。

只跑求職紀錄 API：

```bash
.venv/bin/python -m pytest tests/integration/test_applications.py -q
```

真實外部 API 測試（會使用額度，需要 .env 或環境變數中的 GEMINI_API_KEY 與 FIRECRAWL_API_KEY）：

```bash
.venv/bin/python -m pytest --run-live -m live -v -s
```

完成後停止測試容器：

```bash
docker compose -f docker-compose.test.yml -p job-assistant-tests down
```

測試建表目前使用 ORM metadata，並不驗證 Alembic migration。

## GitHub Actions 自動測試

流程定義在 `.github/workflows/tests.yml`：

1. PR 的目標是 `dev` 或 `main` 時執行，包括 PR 後續更新。
2. 推送／合併到 `dev` 或 `main` 後再次執行。
3. `workflow_dispatch` 提供手動執行入口；通常要等流程合併到預設分支後才會顯示 Run workflow。

工作順序：取出程式碼 → 設定 Python 3.12 → 安裝 requirements-dev.txt → 跑 pytest。
GitHub 另啟動 PostgreSQL 16 service，通過健康檢查後才開始步驟；runner 用 127.0.0.1:5434 連線。
測試仍沿用 conftest 的每案例獨立 schema。服務隨 job 結束移除，這裡的密碼只是暫存測試資料庫的公開測試值。
不需設定正式 DATABASE_URL、AUTH_JWT_SECRET 或 Gemini／Firecrawl secrets。測試自行設定需要的測試值。
`-m "not live"` 排除付費外部服務測試；不要在 CI 加上 `--run-live`。

### 如何確認結果

先 commit、push 功能分支，再建立目標為 dev 的 PR。僅推送功能分支但未建立 PR 不會觸發本流程。
在 PR 的 Checks 或 repository 的 Actions 頁籤查看 `Tests` → `Pytest (Python 3.12)`。
失敗時打開第一個失敗步驟：安裝失敗先看套件版本／下載問題，測試失敗則看 pytest 的案例名稱與 traceback。
目前自動化驗證是後端測試，不包含真實 AI 生成與瀏覽器操作。

這個 workflow 顯示檢查結果，但不會自行禁止合併。
需要強制通過才能合併時，待首次成功執行後，在 GitHub branch ruleset／保護規則中將此 check 設成 required。
本機測試通過不等同 GitHub Ubuntu 執行通過，首次 PR 的執行結果仍需確認。
