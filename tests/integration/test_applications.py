import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Application, CoverLetter, Matching, Resume, Job


@pytest.fixture
async def seed_data(db_session: AsyncSession):
    """建立測試所需的預設資料：Resume, Job, Matching, CoverLetter"""
    resume = Resume(filename="resume.pdf", file_size=128, content_text="Python / Node.js")
    job = Job(source_type="text", raw_content="Backend Engineer at Tech Co",
              parsed_data={"title": "Backend Engineer", "company": "Tech Co"})
    db_session.add_all([resume, job])
    await db_session.commit()
    await db_session.refresh(resume)
    await db_session.refresh(job)

    matching = Matching(
        resume_id=resume.id,
        job_id=job.id,
        score=85,
        match_reasons=["Python skill matched"]
    )
    db_session.add(matching)
    await db_session.commit()
    await db_session.refresh(matching)

    cover_letter = CoverLetter(
        matching_id=matching.id,
        title="Cover Letter 1",
        content="Hello..."
    )
    db_session.add(cover_letter)
    await db_session.commit()
    await db_session.refresh(cover_letter)

    return {
        "resume": resume,
        "job": job,
        "matching": matching,
        "cover_letter": cover_letter,
    }


@pytest.mark.parametrize("with_letter", [True, False], ids=["with-letter", "without-letter"])
@pytest.mark.asyncio
async def test_create_application_success(client: AsyncClient, seed_data: dict, db_session, with_letter):
    payload = {
        "matching_id": seed_data["matching"].id,
        "cover_letter_id": seed_data["cover_letter"].id if with_letter else None,
    }

    expected_resume_id = seed_data["resume"].id
    expected_job_id = seed_data["job"].id
    response = await client.post("/applications", json=payload)

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["message"] == "求職追蹤建立成功"
    assert res_data["data"]["matching_id"] == seed_data["matching"].id
    assert res_data["data"]["cover_letter_id"] == payload["cover_letter_id"]
    assert res_data["data"]["status"] == "preparing"
    db_session.expire_all()
    saved = await db_session.get(Application, res_data["data"]["id"])
    assert saved.resume_id == res_data["data"]["resume_id"] == expected_resume_id
    assert saved.job_id == res_data["data"]["job_id"] == expected_job_id
    assert saved.matching_id == payload["matching_id"]
    assert saved.cover_letter_id == payload["cover_letter_id"]
    assert saved.status == "preparing"


@pytest.mark.asyncio
async def test_create_application_matching_not_found(client: AsyncClient):
    payload = {
        "matching_id": 99999,  
        "cover_letter_id": None,
    }

    response = await client.post("/applications", json=payload)

    assert response.status_code == 404
    assert "Matching 99999 not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_application_invalid_cover_letter(client: AsyncClient, seed_data: dict):
    
    payload = {
        "matching_id": seed_data["matching"].id,
        "cover_letter_id": 88888,  
    }

    response = await client.post("/applications", json=payload)

    assert response.status_code == 404
    assert "not found for this matching" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_application_invalid_body_format(client: AsyncClient):
   
    payload = {
        "matching_id": "not-an-integer",
    }

    response = await client.post("/applications", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_application_cover_letter_from_other_matching(client, seed_data, db_session):
    other = Matching(resume_id=seed_data["resume"].id, job_id=seed_data["job"].id)
    db_session.add(other)
    await db_session.commit()

    response = await client.post("/applications", json={
        "matching_id": other.id,
        "cover_letter_id": seed_data["cover_letter"].id,
    })

    assert response.status_code == 404
    assert "not found for this matching" in response.json()["detail"]
    assert (await db_session.execute(select(Application))).scalars().all() == []


@pytest.mark.asyncio
async def test_list_applications_empty(client):
    response = await client.get("/applications")
    assert response.status_code == 200
    assert response.json() == {
        "message": "查詢成功", "data": [], "total": 0, "limit": 20, "offset": 0,
    }


@pytest.mark.parametrize("with_letter", [True, False])
@pytest.mark.asyncio
async def test_list_applications_details(client, seed_data, db_session, with_letter):
    from datetime import datetime, timezone

    selected = seed_data["cover_letter"]
    row = Application(
        matching_id=seed_data["matching"].id,
        resume_id=seed_data["resume"].id,
        job_id=seed_data["job"].id,
        cover_letter_id=selected.id if with_letter else None,
        status="applied", notes="follow up next week",
        applied_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([row, CoverLetter(
        matching_id=seed_data["matching"].id,
        title="Newer version", content="new text", version=2,
    )])
    await db_session.commit()
    expected_id = row.id
    db_session.expunge_all()

    response = await client.get("/applications")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["data"][0]
    assert item["id"] == expected_id
    assert item["company"] == "Tech Co"
    assert item["job_title"] == "Backend Engineer"
    assert item["resume_filename"] == "resume.pdf"
    assert item["score"] == 85
    assert item["status"] == "applied"
    assert item["notes"] == "follow up next week"
    assert item["applied_at"].startswith("2026-10-01T00:00:00")
    assert item["cover_letter_id"] == (selected.id if with_letter else None)
    assert item["cover_letter_version"] == (1 if with_letter else None)
    assert item["cover_letter_title"] == ("Cover Letter 1" if with_letter else None)


@pytest.mark.asyncio
async def test_list_applications_pagination_and_missing_data(client, seed_data, db_session):
    from datetime import datetime, timezone

    seed_data["job"].parsed_data = None
    seed_data["matching"].score = None
    rows = [Application(
        matching_id=seed_data["matching"].id,
        resume_id=seed_data["resume"].id,
        job_id=seed_data["job"].id,
        user_id=owner,
        created_at=datetime(2026, 10, day, tzinfo=timezone.utc),
    ) for day, owner in [(1, 1), (2, 1), (3, 1), (4, 2)]]
    db_session.add_all(rows)
    await db_session.commit()
    expected_ids = [row.id for row in rows[:3]][::-1]
    db_session.expunge_all()

    response = await client.get("/applications?limit=2&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert [item["id"] for item in body["data"]] == expected_ids[1:]
    assert body["data"][0]["company"] == ""
    assert body["data"][0]["job_title"] == ""
    assert body["data"][0]["score"] is None
    beyond = await client.get("/applications?offset=99")
    assert beyond.json()["data"] == []
    assert beyond.json()["total"] == 3


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
@pytest.mark.asyncio
async def test_list_applications_invalid_pagination(client, query):
    response = await client.get(f"/applications?{query}")
    assert response.status_code == 422
