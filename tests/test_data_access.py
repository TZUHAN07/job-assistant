"""真實 JWT + PostgreSQL 的跨帳號測試；外部 AI/爬蟲全部替身。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select, func

from src.main import app
from src.models import Application, AuthSession, CoverLetter, InterviewSet, Job, Matching, Resume, User
from src.routers import cover_letters, interview_sets, jobs, matchings, resume
from src.services.auth_service import COOKIE_NAME, create_token

pytestmark = pytest.mark.asyncio

# 每個資料端點都必須先驗證身分；含沒有 Request 參數的人工版本 API。
ENDPOINTS = [
    ("GET", "/resumes", {}),
    ("POST", "/resumes/upload", {"files": {"file": ("fake.pdf", b"test", "application/pdf")}}),
    ("DELETE", "/resumes/1", {}),
    ("GET", "/jobs", {}),
    ("POST", "/jobs/parse-text", {"json": {"text": "x" * 60}}),
    ("POST", "/jobs/parse-url", {"json": {"url": "https://example.com/job"}}),
    ("DELETE", "/jobs/1", {}),
    ("POST", "/matchings/score", {"json": {"resume_id": 1, "job_id": 1}}),
    ("GET", "/matchings/1", {}),
    ("DELETE", "/matchings/1", {}),
    ("POST", "/cover-letters/generate", {"json": {"matching_id": 1}}),
    ("GET", "/cover-letters?matching_id=1", {}),
    ("POST", "/cover-letters/1/versions", {"json": {"content": "edited"}}),
    ("GET", "/applications", {}),
    ("POST", "/applications", {"json": {"matching_id": 1}}),
    ("PATCH", "/applications/1", {"json": {"status": "applied"}}),
    ("DELETE", "/applications/1", {}),
    ("POST", "/interview-sets/generate", {"json": {"matching_id": 1}}),
    ("GET", "/interview-sets/latest?matching_id=1", {}),
    ("GET", "/interview-sets/1", {}),
]


@pytest.fixture(autouse=True)
def external_services(monkeypatch):
    mocks = {}
    for module, name in [(resume, "extract_resume_structured"), (jobs, "extract_from_url"),
                         (jobs, "extract_from_text"), (matchings, "calculate_matching_score"),
                         (cover_letters, "generate_reviewed_letter"), (interview_sets, "run_interview")]:
        mock = AsyncMock(side_effect=AssertionError("Unexpected external API call"))
        monkeypatch.setattr(module, name, mock)
        mocks[name] = mock
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[interview_sets.get_interview_client] = lambda: object()
    yield mocks
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


async def graph(db, owner):
    now = datetime.now(timezone.utc)
    r = Resume(user_id=owner, filename=f"owner-{owner}.pdf", file_size=1,
               parsed_data={"name": f"Owner {owner}", "email": "test@example.com"}, processed_at=now)
    j = Job(user_id=owner, source_type="text", raw_content="synthetic",
            parsed_data={"title": "Engineer", "company": f"Company {owner}"}, processed_at=now)
    db.add_all([r, j])
    await db.flush()
    m = Matching(user_id=owner, resume_id=r.id, job_id=j.id, score=80, processed_at=now)
    db.add(m)
    await db.flush()
    c = CoverLetter(user_id=owner, matching_id=m.id, title="Synthetic", content="Private letter")
    i = InterviewSet(user_id=owner, matching_id=m.id, report={})
    db.add_all([c, i])
    await db.flush()
    a = Application(user_id=owner, matching_id=m.id, resume_id=r.id, job_id=j.id, cover_letter_id=c.id)
    db.add(a)
    await db.commit()
    return {"resume": r.id, "job": j.id, "matching": m.id, "letter": c.id, "interview": i.id, "application": a.id}


@pytest.fixture
async def records(authenticated_user, db_session):
    db_session.add(User(id=3, email="other@example.com", password_hash="unused"))
    await db_session.commit()
    return {owner: await graph(db_session, owner) for owner in (2, 3, 1)}


@pytest.mark.parametrize("method,path,kwargs", ENDPOINTS)
async def test_all_data_routes_require_login(client, method, path, kwargs, external_services):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == 401, response.text
    for mock in external_services.values():
        mock.assert_not_awaited()


@pytest.mark.parametrize("origin", [None, "null", "https://evil.example"])
async def test_mutations_require_origin(client, authenticated_user, origin, external_services):
    if origin is None:
        del client.headers["Origin"]
    else:
        client.headers["Origin"] = origin
    for method, path, kwargs in ENDPOINTS:
        if method != "GET":
            response = await client.request(method, path, **kwargs)
            assert response.status_code == 403, (method, path, response.text)
    for mock in external_services.values():
        mock.assert_not_awaited()


async def test_lists_and_account_switch(client, records, db_session):
    for owner in (2, 3):
        if owner == 3:
            expires = datetime.now(timezone.utc) + timedelta(minutes=30)
            db_session.add(AuthSession(id="b" * 64, user_id=3, expires_at=expires))
            await db_session.commit()
            client.cookies.clear()
            client.cookies.set(COOKIE_NAME, create_token(3, "b" * 64, expires))
        for path, key in [("/resumes", "resume"), ("/jobs", "job"), ("/applications", "application")]:
            response = await client.get(path)
            assert response.status_code == 200, response.text
            assert [item["id"] for item in response.json()["data"]] == [records[owner][key]]
        assert (await client.get(f"/matchings/{records[owner]['matching']}")).status_code == 200
        letters = await client.get(f"/cover-letters?matching_id={records[owner]['matching']}")
        assert [row["id"] for row in letters.json()["data"]] == [records[owner]["letter"]]
    # 舊資料只是不可見，沒有被移轉或刪除。
    assert (await db_session.get(Resume, records[1]["resume"])).user_id == 1


@pytest.mark.parametrize("owner", [3, 1])
async def test_foreign_and_legacy_records_are_not_accessible(client, records, owner, db_session, external_services):
    row = records[owner]
    calls = [
        ("DELETE", f"/resumes/{row['resume']}", {}),
        ("DELETE", f"/jobs/{row['job']}", {}),
        ("GET", f"/matchings/{row['matching']}", {}),
        ("DELETE", f"/matchings/{row['matching']}", {}),
        ("GET", f"/cover-letters?matching_id={row['matching']}", {}),
        ("POST", "/cover-letters/generate", {"json": {"matching_id": row["matching"]}}),
        ("POST", f"/cover-letters/{row['letter']}/versions", {"json": {"content": "edited"}}),
        ("POST", "/applications", {"json": {"matching_id": row["matching"]}}),
        ("PATCH", f"/applications/{row['application']}", {"json": {"status": "closed"}}),
        ("DELETE", f"/applications/{row['application']}", {}),
        ("GET", f"/interview-sets/{row['interview']}", {}),
        ("GET", f"/interview-sets/latest?matching_id={row['matching']}", {}),
        ("POST", "/interview-sets/generate", {"json": {"matching_id": row["matching"]}}),
    ]
    for method, path, kwargs in calls:
        response = await client.request(method, path, **kwargs)
        assert response.status_code == 404, (method, path, response.text)
    assert (await db_session.get(Application, row["application"])).status == "preparing"
    for mock in external_services.values():
        mock.assert_not_awaited()


@pytest.mark.parametrize("foreign_source", ["resume", "job"])
async def test_matching_rejects_mixed_owners(client, records, foreign_source, external_services):
    body = {"resume_id": records[2]["resume"], "job_id": records[2]["job"]}
    body[f"{foreign_source}_id"] = records[3][foreign_source]
    response = await client.post("/matchings/score", json=body)
    assert response.status_code == 404
    external_services["calculate_matching_score"].assert_not_awaited()


@pytest.mark.parametrize("foreign_source", ["resume", "job"])
async def test_inconsistent_matching_is_hidden(client, records, db_session, foreign_source, external_services):
    own = records[2]
    row = await db_session.get(Matching, own["matching"])
    setattr(row, f"{foreign_source}_id", records[3][foreign_source])
    await db_session.commit()
    for method, path, kwargs in [
        ("GET", f"/matchings/{own['matching']}", {}),
        ("GET", f"/interview-sets/{own['interview']}", {}),
        ("GET", f"/cover-letters?matching_id={own['matching']}", {}),
        ("POST", "/cover-letters/generate", {"json": {"matching_id": own["matching"]}}),
        ("POST", "/applications", {"json": {"matching_id": own["matching"]}}),
        ("POST", "/interview-sets/generate", {"json": {"matching_id": own["matching"]}}),
    ]:
        response = await client.request(method, path, **kwargs)
        assert response.status_code == 404, response.text
    assert (await client.get("/applications")).json()["data"] == []
    for mock in external_services.values():
        mock.assert_not_awaited()


async def test_application_rejects_foreign_letter_even_if_matching_id_matches(client, records, db_session):
    letter = CoverLetter(user_id=3, matching_id=records[2]["matching"], title="private", content="private")
    db_session.add(letter)
    await db_session.commit()
    response = await client.post("/applications", json={"matching_id": records[2]["matching"], "cover_letter_id": letter.id})
    assert response.status_code == 404


async def test_creations_use_session_owner(client, records, db_session, monkeypatch, external_services):
    # 上游只模擬輸出；資料存檔、權限與交易仍使用正式程式。
    for name in ["extract_resume_structured", "extract_from_text", "calculate_matching_score"]:
        external_services[name].side_effect = None
        external_services[name].return_value = None  # partial-save 仍須寫入正確擁有者
    external_services["extract_from_url"].side_effect = None
    external_services["extract_from_url"].return_value = ("synthetic", None)
    external_services["generate_reviewed_letter"].side_effect = None
    external_services["generate_reviewed_letter"].return_value = (SimpleNamespace(
        title="Generated", full_content="test", opening="a", why_me="b", why_company="c", call_to_action="d"), None)
    monkeypatch.setattr(resume, "PdfReader", Mock(return_value=SimpleNamespace(pages=[])))
    own = records[2]
    cases = [
        ("/resumes/upload", {"files": {"file": ("test.pdf", b"fake", "application/pdf")}}, Resume),
        ("/jobs/parse-text", {"json": {"text": "x" * 60, "user_id": 3}}, Job),
        ("/jobs/parse-url", {"json": {"url": "https://example.com/job", "user_id": 3}}, Job),
        ("/matchings/score", {"json": {"resume_id": own["resume"], "job_id": own["job"], "user_id": 3}}, Matching),
        ("/cover-letters/generate", {"json": {"matching_id": own["matching"], "user_id": 3}}, CoverLetter),
        (f"/cover-letters/{own['letter']}/versions", {"json": {"content": "edited"}}, CoverLetter),
        ("/applications", {"json": {"matching_id": own["matching"], "cover_letter_id": own["letter"], "user_id": 3}}, Application),
    ]
    for path, kwargs, model in cases:
        response = await client.post(path, **kwargs)
        assert response.status_code == 201, (path, response.text)
        saved = await db_session.get(model, response.json()["data"]["id"])
        assert saved.user_id == 2


async def test_owner_can_update_and_delete(client, records, db_session):
    own = records[2]
    response = await client.patch(f"/applications/{own['application']}", json={"status": "interview"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "interview"
    for path in [f"/applications/{own['application']}", f"/matchings/{own['matching']}",
                 f"/resumes/{own['resume']}", f"/jobs/{own['job']}"]:
        response = await client.delete(path)
        assert response.status_code == 204, response.text
    assert (await db_session.get(Resume, records[3]["resume"])).user_id == 3


async def test_logout_revokes_data_access(client, authenticated_user):
    assert (await client.get("/resumes")).status_code == 200
    token = client.cookies.get(COOKIE_NAME)
    assert (await client.post("/auth/logout")).status_code == 200
    client.cookies.set(COOKIE_NAME, token)
    assert (await client.get("/resumes")).status_code == 401


@pytest.mark.parametrize("resource", ["resumes", "jobs", "matchings"])
async def test_owner_deletion_cascades_only_own_graph(client, records, db_session, resource):
    own = records[2]
    key = {"resumes": "resume", "jobs": "job", "matchings": "matching"}[resource]
    response = await client.delete(f"/{resource}/{own[key]}")
    assert response.status_code == 204, response.text
    # 用 SQL 重新查詢，避開已載入 ORM 物件的記憶體快取。
    for model, name in [(Matching, "matching"), (CoverLetter, "letter"),
                        (InterviewSet, "interview"), (Application, "application")]:
        assert await db_session.scalar(select(func.count()).select_from(model).where(model.id == own[name])) == 0
        assert await db_session.scalar(select(func.count()).select_from(model).where(model.id == records[3][name])) == 1


async def test_cross_site_header_rejected(client, authenticated_user):
    response = await client.post("/applications", json={"matching_id": 1}, headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
