import copy
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import httpx
from google.genai import errors
from sqlalchemy import func, select

from src.models import InterviewSet, Job, Matching, Resume
from src.routers import interview_sets as api
from src.main import app


@pytest.fixture
def fake_generator(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": 1,
        "matching_id": 1,
        "created_at": now,
        "model": "test-model",
        "model_rounds": 2,
        "tool_calls": 2,
        "validation": "test",
        "sources": {},
        "evidence_catalog": {},
        "questions": [
            {
                "question": f"題目 {i}",
                "kind": "hypothetical",
                "rationale": "職缺需求",
                "job_evidence_ids": ["job:1:skill:0"],
                "resume_evidence_ids": [],
                "job_evidence": [{"id": "job:1:skill:0", "text": "Python"}],
                "resume_evidence": [],
            }
            for i in range(5)
        ],
    }

    async def generate(client, matching_id, *, user_id):
        value = copy.deepcopy(report)
        value["matching_id"] = matching_id
        return value

    mock = AsyncMock(side_effect=generate)
    monkeypatch.setattr(api, "run_interview", mock)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[api.get_interview_client] = lambda: object()
    try:
        yield mock
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


async def seed(db, *, owner=1, resume_owner=None, ready=True):
    now = datetime.now(timezone.utc)
    resume = Resume(
        user_id=owner if resume_owner is None else resume_owner,
        filename="synthetic.pdf",
        file_size=1,
        parsed_data={"test": True},
        processed_at=now if ready else None,
    )
    job = Job(
        user_id=owner,
        source_type="text",
        raw_content="synthetic",
        parsed_data={"test": True},
        processed_at=now,
    )
    db.add_all([resume, job])
    await db.flush()
    matching = Matching(user_id=owner, resume_id=resume.id, job_id=job.id)
    db.add(matching)
    await db.commit()
    return matching.id


@pytest.mark.asyncio
async def test_generate_and_preserve_previous_set(client, db_session, fake_generator):
    matching_id = await seed(db_session)
    first = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    second = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    assert first.status_code == second.status_code == 201
    a, b = first.json()["data"], second.json()["data"]
    assert a["id"] != b["id"]
    assert len(a["report"]["questions"]) == 5
    saved = await db_session.get(InterviewSet, a["id"])
    assert saved.user_id == 1 and saved.report == a["report"]
    assert await db_session.scalar(select(func.count()).select_from(InterviewSet)) == 2
    assert fake_generator.await_args.kwargs == {"user_id": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [{}, {"matching_id": 0}, {"matching_id": "63"}, {"matching_id": 1, "user_id": 2}],
)
async def test_invalid_request(client, db_session, fake_generator, body):
    response = await client.post("/interview-sets/generate", json=body)
    assert response.status_code == 422
    fake_generator.assert_not_awaited()
    assert await db_session.scalar(select(func.count()).select_from(InterviewSet)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,status",
    [
        ("missing", 404),
        ("other_owner", 404),
        ("other_resume_owner", 404),
        ("unready", 409),
    ],
)
async def test_unusable_source(client, db_session, fake_generator, case, status):
    matching_id = (
        999999
        if case == "missing"
        else await seed(
            db_session,
            owner=2 if case == "other_owner" else 1,
            resume_owner=2 if case == "other_resume_owner" else None,
            ready=case != "unready",
        )
    )
    response = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    assert response.status_code == status
    fake_generator.assert_not_awaited()
    assert await db_session.scalar(select(func.count()).select_from(InterviewSet)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,status,message",
    [
        (ValueError("private resume must not leak"), 502, "內容驗證未通過"),
        (TimeoutError(), 504, "逾時"),
        (errors.ServerError(503, {"error": {"message": "private resume"}}), 502, "AI 服務回應失敗"),
        (errors.ClientError(429, {"error": {"message": "private resume"}}), 502, "額度或請求頻率受限"),
        (httpx.ConnectError("private resume"), 502, "AI 服務連線"),
    ],
)
async def test_generation_failure_not_saved(
    client, db_session, fake_generator, error, status, message
):
    matching_id = await seed(db_session)
    fake_generator.side_effect = error
    response = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    assert response.status_code == status
    assert message in response.json()["detail"]
    assert "private resume" not in response.text
    assert await db_session.scalar(select(func.count()).select_from(InterviewSet)) == 0


@pytest.mark.asyncio
async def test_commit_failure_rolls_back(
    client, db_session, fake_generator, monkeypatch
):
    matching_id = await seed(db_session)
    monkeypatch.setattr(
        db_session, "commit", AsyncMock(side_effect=RuntimeError("storage failure"))
    )
    response = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    assert response.status_code == 500
    assert await db_session.scalar(select(func.count()).select_from(InterviewSet)) == 0


@pytest.mark.asyncio
async def test_get_saved_snapshot_without_ai(
    client, db_session, fake_generator, monkeypatch
):
    matching_id = await seed(db_session)
    created = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    assert created.status_code == 201
    saved = created.json()["data"]
    fake_generator.reset_mock()

    # GET 必須不依賴 Gemini client，即使沒有 API key 仍可查詢。
    def forbidden_client():
        raise AssertionError("GET must not create a Gemini client")

    app.dependency_overrides[api.get_interview_client] = forbidden_client
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    matching = await db_session.get(Matching, matching_id)
    resume = await db_session.get(Resume, matching.resume_id)
    resume.parsed_data = {"changed": True}
    await db_session.commit()
    for _ in range(2):
        response = await client.get(f"/interview-sets/{saved['id']}")
        assert response.status_code == 200
        assert response.json()["data"] == saved
    fake_generator.assert_not_awaited()
    assert await db_session.scalar(select(func.count()).select_from(InterviewSet)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,status", [("0", 422), ("-1", 422), ("abc", 422), ("999999", 404)]
)
async def test_get_invalid_or_missing(client, fake_generator, path, status):
    response = await client.get(f"/interview-sets/{path}")
    assert response.status_code == status
    fake_generator.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_other_owner_returns_same_404(client, db_session, fake_generator):
    matching_id = await seed(db_session)
    created = await client.post(
        "/interview-sets/generate", json={"matching_id": matching_id}
    )
    row = await db_session.get(InterviewSet, created.json()["data"]["id"])
    row.user_id = 2
    await db_session.commit()
    fake_generator.reset_mock()
    denied = await client.get(f"/interview-sets/{row.id}")
    missing = await client.get("/interview-sets/999999")
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()
    fake_generator.assert_not_awaited()


@pytest.mark.asyncio
async def test_latest_empty_then_newest_summary(client, db_session, fake_generator):
    matching_id = await seed(db_session)
    url = f"/interview-sets/latest?matching_id={matching_id}"
    empty = await client.get(url)
    assert empty.status_code == 200 and empty.json()["data"] is None
    fake_generator.assert_not_awaited()
    ids = []
    for _ in range(2):
        created = await client.post(
            "/interview-sets/generate", json={"matching_id": matching_id}
        )
        ids.append(created.json()["data"]["id"])
    # 固定時間驗證 ID 的次排序，並讓別人的題組具有更大的 ID。
    first = await db_session.get(InterviewSet, ids[0])
    second = await db_session.get(InterviewSet, ids[1])
    second.created_at = first.created_at
    db_session.add(InterviewSet(user_id=2, matching_id=matching_id, report={}))
    await db_session.commit()
    fake_generator.reset_mock()
    latest = await client.get(url)
    assert latest.status_code == 200
    assert latest.json()["data"]["id"] == ids[1]
    assert set(latest.json()["data"]) == {"id", "matching_id", "created_at"}
    fake_generator.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,status",
    [
        ("", 422),
        ("?matching_id=0", 422),
        ("?matching_id=abc", 422),
        ("?matching_id=999999", 404),
    ],
)
async def test_latest_invalid_matching(client, fake_generator, query, status):
    response = await client.get("/interview-sets/latest" + query)
    assert response.status_code == status
    fake_generator.assert_not_awaited()


@pytest.mark.asyncio
async def test_latest_other_matching_owner(client, db_session, fake_generator):
    matching_id = await seed(db_session, owner=2)
    response = await client.get(f"/interview-sets/latest?matching_id={matching_id}")
    assert response.status_code == 404
    fake_generator.assert_not_awaited()
