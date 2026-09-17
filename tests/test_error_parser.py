from src.services.cover_letter_service import parse_quota_error

def test_daily_quota_error():
    error = "429 RESOURCE_EXHAUSTED PerDay quota exceeded"

    result = parse_quota_error(error)

    assert result == "AI 服務今日額度已用完，請明天再試"

def test_retry_delay_error():
    error = '429 RESOURCE_EXHAUSTED retryDelay: "23s"'

    result = parse_quota_error(error)

    assert result == "AI 服務目前請求過於頻繁，請約 23 秒後再試"


def test_unknown_quota_error():
    error = "429 RESOURCE_EXHAUSTED"

    result = parse_quota_error(error)

    assert result == "AI 服務目前請求量較大，請稍後再試"

def test_daily_quota_case_insensitive():
    error = "429 RESOURCE_EXHAUSTED DAILY QUOTA EXCEEDED"

    result = parse_quota_error(error)

    assert result == "AI 服務今日額度已用完，請明天再試"