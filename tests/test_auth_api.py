import pytest
from sqlalchemy import select, func
from src.models.user import User
from src.services.password_service import password_hasher

PASSWORD = 'test-only-long-password'


@pytest.fixture(autouse=True)
def auth_origin(client, monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://test")
    client.headers["Origin"] = "http://test"



@pytest.mark.asyncio
async def test_register_hash_and_duplicate(client, db_session):
    response = await client.post('/auth/register', json={'email': 'Test@EXAMPLE.com', 'password': PASSWORD})
    assert response.status_code == 201
    assert response.json()['data']['id'] >= 2
    assert response.json()['data']['email'] == 'test@example.com'
    assert PASSWORD not in response.text
    assert 'password_hash' not in response.text
    user = await db_session.scalar(select(User))
    assert user.password_hash.startswith('$argon2id$')
    assert password_hasher.verify(PASSWORD, user.password_hash)
    assert not password_hasher.verify('wrong-password', user.password_hash)
    duplicate = await client.post('/auth/register', json={'email': 'TEST@example.com', 'password': PASSWORD})
    assert duplicate.status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [
    {'email': 'bad', 'password': PASSWORD},
    {'email': 'test@example.com', 'password': 'short-secret'},
    {'email': 'test@example.com', 'password': 'x' * 129},
    {'email': 'test@example.com', 'password': PASSWORD, 'user_id': 1},
    {'email': 'test@example.com'},
])
async def test_invalid_registration_does_not_leak_or_save(client, db_session, body):
    response = await client.post('/auth/register', json=body)
    assert response.status_code == 422
    assert body.get('password', PASSWORD) not in response.text
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.asyncio
async def test_registration_commit_failure_rolls_back(client, db_session, monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setattr(db_session, 'commit', AsyncMock(side_effect=RuntimeError(PASSWORD)))
    response = await client.post('/auth/register', json={'email': 'test@example.com', 'password': PASSWORD})
    assert response.status_code == 500
    assert PASSWORD not in response.text
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.asyncio
async def test_users_migration_upgrade_and_downgrade(db_session):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('users_migration', Path(__file__).resolve().parents[1] / 'alembic/versions/e30authusers_create_users.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    connection = await db_session.connection()
    def exercise(sync_connection):
        from src.models.auth_session import AuthSession
        AuthSession.__table__.drop(sync_connection)
        User.__table__.drop(sync_connection)
        with Operations.context(MigrationContext.configure(sync_connection)):
            migration.upgrade()
            row_id = sync_connection.scalar(text("INSERT INTO users (email, password_hash) VALUES ('migration@example.com', 'test-only') RETURNING id"))
            assert row_id == 2
            migration.downgrade()
            assert sync_connection.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='users'")) == 0
    await connection.run_sync(exercise)
