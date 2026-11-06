import ssl

from src.database_url import async_database_options, sync_database_url


def test_local_url_keeps_connection_unmodified():
    url, args = async_database_options("postgresql+asyncpg://user:pass@localhost/db")
    assert url.drivername == "postgresql+asyncpg"
    assert args == {}


def test_neon_uses_verified_tls_without_libpq_options():
    value = "postgresql://user:p%25ss@host/db?sslmode=require&channel_binding=require&connect_timeout=15"
    url, args = async_database_options(value)
    assert url.password == "p%ss"
    assert not url.query
    assert args["timeout"] == 15
    assert args["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert args["ssl"].check_hostname
    sync = sync_database_url(value)
    assert sync.drivername == "postgresql+psycopg2"
    assert sync.query["channel_binding"] == "require"
    assert sync.password == "p%ss"
