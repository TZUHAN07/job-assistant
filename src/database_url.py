"""將標準 PostgreSQL URL 轉成各驅動可接受的連線設定。"""
import ssl

import certifi

from sqlalchemy.engine import make_url


def async_database_options(value: str):
    url = make_url(value).set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    options = {}
    mode = query.pop("sslmode", None)
    # asyncpg 不接受 libpq 的 channel_binding 參數；以憑證與主機驗證保護 TLS。
    binding = query.pop("channel_binding", None)
    if mode in {"require", "verify-ca", "verify-full"} or binding == "require":
        options["ssl"] = ssl.create_default_context(cafile=certifi.where())
    elif mode is not None:
        options["ssl"] = mode
    timeout = query.pop("connect_timeout", None)
    if timeout is not None:
        options["timeout"] = float(timeout)
    return url.set(query=query), options


def sync_database_url(value: str):
    # Alembic 使用 psycopg2，保留它支援的 SSL 與 channel_binding 參數。
    return make_url(value).set(drivername="postgresql+psycopg2")
