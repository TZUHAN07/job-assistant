from datetime import datetime, timezone
from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from src.models import Resume, Job, Matching, CoverLetter, CoverLetterTemplate
from src.schemas import ResumeParsed, JobParsed
from src.schemas.cover_letter_review import CoverLetterReview
from src.services import cover_letter_template_service as service
from src.routers import cover_letters

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def graph(authenticated_user, db_session):
    now = datetime.now(timezone.utc)
    r = Resume(user_id=2, filename="synthetic.pdf", file_size=1,
               parsed_data={"name": "Test", "email": "test@example.com"}, processed_at=now)
    j = Job(user_id=2, source_type="text", raw_content="synthetic",
            parsed_data={"company": "Example", "title": "Designer"}, processed_at=now)
    db_session.add_all([r, j]); await db_session.flush()
    m = Matching(user_id=2, resume_id=r.id, job_id=j.id, score=80, processed_at=now)
    db_session.add(m); await db_session.commit()
    return r, j, m


def body(m):
    return dict(matching_id=m.id, name="Design", language="zh-TW",
                opening="{{company}} 您好，我應徵 {{job_title}}。",
                why_me="在個人作品中完成原型。", call_to_action="作品連結與署名")


async def test_unauthenticated(client):
    assert (await client.get("/cover-letter-templates?matching_id=1")).status_code == 401
    assert (await client.post("/cover-letter-templates", json=body(SimpleNamespace(id=1)))).status_code == 401


async def test_immutable_templates_and_resume_binding(client, db_session, graph):
    r, j, m = graph
    first = await client.post("/cover-letter-templates", json=body(m))
    assert first.status_code == 201, first.text
    first_id = first.json()["data"]["id"]
    changed = {**body(m), "why_me": "更新作品描述"}
    second = await client.post("/cover-letter-templates", json=changed)
    assert second.json()["data"]["id"] != first_id
    original = await db_session.get(CoverLetterTemplate, first_id)
    assert original.why_me == body(m)["why_me"]
    # 同份履歷的另一個職缺可共用；不同履歷不得共用。
    m2 = Matching(user_id=2, resume_id=r.id, job_id=j.id, score=80, processed_at=m.processed_at)
    db_session.add(m2); await db_session.commit()
    data = (await client.get(f"/cover-letter-templates?matching_id={m2.id}")).json()["data"]
    assert len(data) == 2 and not any(t["stale"] for t in data)
    r.parsed_data = {**r.parsed_data, "summary": "changed"}; await db_session.commit()
    data = (await client.get(f"/cover-letter-templates?matching_id={m.id}")).json()["data"]
    assert all(t["stale"] for t in data)
    res = await client.post("/cover-letters/generate", json={"matching_id": m.id, "template_id": first_id})
    assert res.status_code == 409


@pytest.mark.parametrize("field,value", [("opening", "no placeholders"), ("why_me", "{{unknown}}"), ("why_me", " ")])
async def test_invalid_template(client, graph, field, value):
    response = await client.post("/cover-letter-templates", json={**body(graph[2]), field: value})
    assert response.status_code == 422


async def test_foreign_matching_hidden(client, db_session, graph):
    r, j, m = graph
    r.user_id = 3; await db_session.commit()
    assert (await client.get(f"/cover-letter-templates?matching_id={m.id}")).status_code == 404
    assert (await client.post("/cover-letter-templates", json=body(m))).status_code == 404


async def test_wrong_resume_template_rejected_before_ai(client, db_session, graph, monkeypatch):
    r, j, m = graph
    created = (await client.post("/cover-letter-templates", json=body(m))).json()["data"]
    other = Resume(user_id=2, filename="other.pdf", file_size=1, parsed_data=r.parsed_data)
    db_session.add(other); await db_session.flush()
    t = await db_session.get(CoverLetterTemplate, created["id"])
    t.resume_id = other.id; await db_session.commit()
    fake = AsyncMock(); monkeypatch.setattr(cover_letters, "generate_from_template", fake)
    res = await client.post("/cover-letters/generate", json={"matching_id": m.id, "template_id": t.id})
    assert res.status_code == 404
    fake.assert_not_awaited()


async def test_fixed_sections_review_and_snapshot(client, db_session, graph, monkeypatch):
    r, j, m = graph
    created = (await client.post("/cover-letter-templates", json=body(m))).json()["data"]
    reviewer = AsyncMock(return_value=CoverLetterReview(status="review_failed", error="test timeout"))
    monkeypatch.setattr(service, "review_cover_letter", reviewer)
    fake_client = SimpleNamespace(create=AsyncMock(return_value=service.JobConnection(why_company="第三段內容")))
    async def generate(resume, job, template):
        return await service.generate_from_template(resume, job, template, client=fake_client)
    monkeypatch.setattr(cover_letters, "generate_from_template", generate)
    res = await client.post("/cover-letters/generate", json={"matching_id": m.id, "template_id": created["id"]})
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["sections"]["opening"] == "Example 您好，我應徵 Designer。"
    assert data["sections"]["why_me"] == body(m)["why_me"]
    assert data["sections"]["call_to_action"] == body(m)["call_to_action"]
    assert data["content"] == "\n\n".join(data["sections"].values())
    assert data["review_metadata"]["status"] == "review_failed"
    assert data["review_metadata"]["template_snapshot"]["id"] == created["id"]
    stored = await db_session.get(CoverLetter, data["id"])
    assert stored.content == data["content"]
    assert fake_client.create.await_count == 1
    assert reviewer.await_count == 1


async def test_placeholder_values_are_not_recursively_interpreted():
    job = JobParsed(company="{{job_title}} Corp", title="Role")
    assert service.render_fixed("{{company}} / {{job_title}}", job) == "{{job_title}} Corp / Role"


async def test_migration_roundtrip(db_session):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    path = Path(__file__).parents[1] / "alembic/versions/g09lettertemplates.py"
    spec = importlib.util.spec_from_file_location("template_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def roundtrip(connection):
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            assert "cover_letter_templates" not in inspect(connection).get_table_names()
            migration.upgrade()
            inspector = inspect(connection)
            assert "cover_letter_templates" in inspector.get_table_names()
            indexes = {i["name"] for i in inspector.get_indexes("cover_letter_templates")}
            assert indexes == {"ix_cover_letter_templates_user_id", "ix_cover_letter_templates_resume_id"}

    await (await db_session.connection()).run_sync(roundtrip)


async def test_language_mismatch_rejected_before_ai(client, graph, monkeypatch):
    m = graph[2]
    created = (await client.post("/cover-letter-templates", json=body(m))).json()["data"]
    fake = AsyncMock()
    monkeypatch.setattr(cover_letters, "generate_from_template", fake)
    response = await client.post("/cover-letters/generate", json={
        "matching_id": m.id, "template_id": created["id"], "language": "en-US"})
    assert response.status_code == 409
    fake.assert_not_awaited()
