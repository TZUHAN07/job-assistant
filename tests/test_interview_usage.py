import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from src.services import interview_usage as usage_module
from src.services import interview_service as service


def fake_client(outcomes):
    iterator = iter(outcomes)
    def generate_content(**kwargs):
        outcome = next(iterator)
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(usage_metadata=outcome)
    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', [False, True])
async def test_round_usage_and_unknown_totals(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(usage_module, 'USAGE_DIR', tmp_path)
    metadata = SimpleNamespace(prompt_token_count=10, candidates_token_count=2,
                               thoughts_token_count=3, total_token_count=15)
    tracker = usage_module.InterviewUsage(72)
    client = fake_client([metadata, None if missing else metadata])
    await tracker.generate(client)
    await tracker.generate(client)
    tracker.finish('generation_succeeded')
    data = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert len(data['rounds']) == 2
    assert data['totals']['total_token_count'] == (None if missing else 30)
    assert data['totals']['cached_content_token_count'] is None
    assert data['duration_ms'] >= 0


@pytest.mark.asyncio
async def test_failed_call_keeps_prior_usage(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_module, 'USAGE_DIR', tmp_path)
    tracker = usage_module.InterviewUsage(72)
    client = fake_client([SimpleNamespace(total_token_count=15), TimeoutError('private')])
    await tracker.generate(client)
    with pytest.raises(TimeoutError):
        await tracker.generate(client)
    tracker.finish('failed', 'TimeoutError')
    text = next(tmp_path.glob('*.json')).read_text()
    data = json.loads(text)
    assert data['rounds'][0]['total_token_count'] == 15
    assert data['rounds'][1]['error_type'] == 'TimeoutError'
    assert data['totals']['total_token_count'] is None
    assert 'private' not in text


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [None, ValueError('private evidence')])
async def test_service_finalizes_validation_result(tmp_path, monkeypatch, error):
    monkeypatch.setattr(usage_module, 'USAGE_DIR', tmp_path)
    monkeypatch.setattr(service, '_run_interview', AsyncMock(return_value={'ok': True}, side_effect=error))
    if error:
        with pytest.raises(ValueError):
            await service.run_interview(None, 72)
    else:
        assert await service.run_interview(None, 72) == {'ok': True}
    text = next(tmp_path.glob('*.json')).read_text()
    data = json.loads(text)
    assert data['status'] == ('failed' if error else 'generation_succeeded')
    assert 'private evidence' not in text


def test_write_failure_does_not_raise(tmp_path, monkeypatch, caplog):
    target = tmp_path / 'file'
    target.write_text('not a directory')
    monkeypatch.setattr(usage_module, 'USAGE_DIR', target)
    usage_module.InterviewUsage(72).finish('failed', 'ValueError')
    assert 'Interview usage write failed' in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [429, 500, 503])
async def test_upstream_code_is_recorded_without_private_response(tmp_path, monkeypatch, code):
    from google.genai import errors
    monkeypatch.setattr(usage_module, "USAGE_DIR", tmp_path)
    tracker = usage_module.InterviewUsage(72)
    error = errors.APIError(code, {"error": {"message": "private resume"}})
    with pytest.raises(errors.APIError):
        await tracker.generate(fake_client([error]))
    tracker.finish("failed", type(error).__name__)
    text = next(tmp_path.glob("*.json")).read_text()
    data = json.loads(text)
    assert data["rounds"][0]["upstream_status_code"] == code
    assert data["rounds"][0]["total_token_count"] is None
    assert "private resume" not in text
