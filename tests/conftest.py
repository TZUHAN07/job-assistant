import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://jobassistant_test:test_only_password@127.0.0.1:5434/job_assistant_test",
)
url = make_url(TEST_DATABASE_URL)
if url.drivername != "postgresql+asyncpg" or not (url.database or "").endswith("_test"):
    raise pytest.UsageError("TEST_DATABASE_URL must use postgresql+asyncpg and a database ending in _test")


os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Enable tests that call paid external APIs")


def pytest_configure(config):
    if config.getoption("--run-live"):
        from dotenv import load_dotenv
        load_dotenv()
        missing = [key for key in ("GEMINI_API_KEY", "FIRECRAWL_API_KEY") if not os.getenv(key)]
        if missing:
            raise pytest.UsageError("Live tests require: " + ", ".join(missing))
    else:
        # 本機 API 測試不需要真實金鑰；client 在 import 時仍需要非空值。
        os.environ["GEMINI_API_KEY"] = "test-placeholder"
        os.environ["GOOGLE_API_KEY"] = "test-placeholder"
        os.environ["FIRECRAWL_API_KEY"] = "test-placeholder"


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip = pytest.mark.skip(reason="External API test; explicitly enable with --run-live")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)


@pytest_asyncio.fixture
async def db_session():
    from src.models import Base

    # 每個測試各自使用 schema，避免 commit 或平行執行污染其他測試。
    schema = "test_" + uuid4().hex
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"timeout": 5, "command_timeout": 10,
                      "server_settings": {"search_path": schema}},
    )
    created = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.run_sync(Base.metadata.create_all)
        created = True
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            yield session
    finally:
        try:
            if created:
                async with engine.begin() as conn:
                    await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    from httpx import ASGITransport, AsyncClient
    from src.database import get_db
    from src.limiter import limiter
    from src.main import app

    async def override_get_db():
        yield db_session

    class BoundedAsyncClient(AsyncClient):
        async def send(self, request, **kwargs):
           
            async with asyncio.timeout(3.5):
                return await super().send(request, **kwargs)

    previous_overrides = app.dependency_overrides.copy()
    previous_enabled = limiter.enabled
    app.dependency_overrides[get_db] = override_get_db
    limiter.enabled = False
    try:
        transport = ASGITransport(app=app)
        async with BoundedAsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        limiter.enabled = previous_enabled
