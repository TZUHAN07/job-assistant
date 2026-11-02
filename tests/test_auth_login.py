from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from sqlalchemy import select, func
from src.models import User, AuthSession
from src.services.auth_service import COOKIE_NAME, ISSUER, AUDIENCE
from src.services.password_service import hash_password

PASSWORD = 'test-only-long-password'
SECRET = 'test-key-not-for-production-use-1234567890'


@pytest.fixture(autouse=True)
def settings(client, monkeypatch):
    monkeypatch.setenv('AUTH_JWT_SECRET', SECRET)
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost')
    monkeypatch.setenv('AUTH_COOKIE_SECURE', 'false')
    client.headers['Origin'] = 'http://localhost'


async def seed(db):
    user = User(email='login@example.com', password_hash=hash_password(PASSWORD))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(client, **changes):
    return await client.post('/auth/login', json={'email': 'login@example.com', 'password': PASSWORD, **changes})


@pytest.mark.asyncio
async def test_login_me_logout_and_replay(client, db_session):
    user = await seed(db_session)
    response = await login(client)
    assert response.status_code == 200
    assert PASSWORD not in response.text and 'password_hash' not in response.text
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Max-Age=1800' in cookie
    assert response.headers['cache-control'] == 'no-store'
    token = client.cookies.get(COOKIE_NAME)
    assert token and token not in response.text
    result = await client.get('/auth/me')
    assert result.status_code == 200 and result.json()['data']['id'] == user.id
    assert (await client.post('/auth/logout')).status_code == 200
    assert (await client.get('/auth/me')).status_code == 401
    client.cookies.set(COOKIE_NAME, token)
    assert (await client.get('/auth/me')).status_code == 401
    session = await db_session.scalar(select(AuthSession))
    assert session.revoked_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['wrong_password', 'missing_user', 'disabled'])
async def test_invalid_login_is_generic(client, db_session, case):
    if case != 'missing_user':
        user = await seed(db_session)
        if case == 'disabled':
            user.is_active = False
            await db_session.commit()
    response = await login(client, password='wrong' if case == 'wrong_password' else PASSWORD)
    assert response.status_code == 401
    assert response.json()['detail'] == 'Email 或密碼不正確'
    assert 'set-cookie' not in response.headers
    assert await db_session.scalar(select(func.count()).select_from(AuthSession)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('case', ['missing', 'tampered', 'expired_jwt', 'expired_session', 'disabled', 'missing_claim', 'wrong_audience', 'wrong_owner', 'unknown_session'])
async def test_invalid_session(client, db_session, case):
    user = await seed(db_session)
    assert (await login(client)).status_code == 200
    token = client.cookies.get(COOKIE_NAME)
    claims = jwt.decode(token, SECRET, algorithms=['HS256'], audience=AUDIENCE, issuer=ISSUER)
    if case == 'expired_session':
        session = await db_session.scalar(select(AuthSession))
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db_session.commit()
    elif case == 'disabled':
        user.is_active = False
        await db_session.commit()
    elif case == 'expired_jwt':
        claims['exp'] = int((datetime.now(timezone.utc) - timedelta(seconds=1)).timestamp())
    elif case == 'missing_claim':
        del claims['exp']
    elif case == 'wrong_audience':
        claims['aud'] = 'other'
    elif case == 'wrong_owner':
        claims['sub'] = str(user.id + 1)
    elif case == 'unknown_session':
        claims['sid'] = '0' * 64
    client.cookies.clear()
    if case != 'missing':
        client.cookies.set(COOKIE_NAME, 'invalid.token' if case == 'tampered' else jwt.encode(claims, SECRET, algorithm='HS256'))
    response = await client.get('/auth/me')
    assert response.status_code == 401
    assert response.json()['detail'] == '請重新登入'


@pytest.mark.asyncio
@pytest.mark.parametrize('origin', [None, 'null', 'https://evil.example', 'http://localhost.evil.example'])
async def test_cross_origin_rejected(client, db_session, origin):
    await seed(db_session)
    await login(client)
    client.headers.pop('Origin')
    if origin is not None:
        client.headers['Origin'] = origin
    assert (await login(client)).status_code == 403
    assert (await client.post('/auth/logout')).status_code == 403
    assert (await client.post('/auth/register', json={'email':'other@example.com', 'password':PASSWORD})).status_code == 403
    assert (await client.get('/auth/me')).status_code == 200


@pytest.mark.asyncio
async def test_missing_secret_fails_closed(client, db_session, monkeypatch):
    await seed(db_session)
    monkeypatch.delenv('AUTH_JWT_SECRET')
    response = await login(client)
    assert response.status_code == 503
    assert 'set-cookie' not in response.headers
    assert await db_session.scalar(select(func.count()).select_from(AuthSession)) == 0


@pytest.mark.asyncio
async def test_secure_cookie_and_login_commit_failure(client, db_session, monkeypatch):
    await seed(db_session)
    monkeypatch.setenv('AUTH_COOKIE_SECURE', 'true')
    response = await login(client)
    assert response.status_code == 200 and 'Secure' in response.headers['set-cookie']
    monkeypatch.setattr(db_session, 'commit', AsyncMock(side_effect=RuntimeError('secret details')))
    response = await login(client)
    assert response.status_code == 500 and 'secret details' not in response.text
    assert 'set-cookie' not in response.headers
    assert await db_session.scalar(select(func.count()).select_from(AuthSession)) == 1


@pytest.mark.asyncio
async def test_logout_commit_failure_keeps_session(client, db_session, monkeypatch):
    await seed(db_session)
    await login(client)
    monkeypatch.setattr(db_session, 'commit', AsyncMock(side_effect=RuntimeError('secret details')))
    response = await client.post('/auth/logout')
    assert response.status_code == 500
    assert 'set-cookie' not in response.headers
    assert (await client.get('/auth/me')).status_code == 200


@pytest.mark.asyncio
async def test_sessions_migration(db_session):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    spec = importlib.util.spec_from_file_location('session_migration', Path(__file__).resolve().parents[1] / 'alembic/versions/f30authsessions_create_auth_sessions.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await db_session.connection()
    def exercise(conn):
        AuthSession.__table__.drop(conn)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert inspect(conn).has_table('auth_sessions')
            assert inspect(conn).get_foreign_keys('auth_sessions')[0]['referred_table'] == 'users'
            migration.downgrade()
            assert not inspect(conn).has_table('auth_sessions')
    await connection.run_sync(exercise)
