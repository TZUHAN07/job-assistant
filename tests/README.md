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
