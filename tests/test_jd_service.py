import asyncio

import pytest

from src.services.jd_service import extract_from_url, extract_from_text

pytestmark = pytest.mark.live

YOURATOR_URL = "https://www.yourator.co/companies/Tricuss/jobs/47778"

PASTE_JD = """
# 資深後端工程師 (Senior Backend Engineer)

十論科技股份有限公司 - Taipei, Taiwan

## 職務內容
- 使用 Python + FastAPI 開發 AI 應用後端
- 設計 RESTful API + database schema
- 整合 LLM API (Anthropic / OpenAI / Gemini)

## 必要條件
- 3 年以上後端開發經驗
- 熟悉 Python + async framework
- 熟悉 PostgreSQL / Docker

## 加分條件
- LangChain / Instructor 經驗
- CI/CD 熟悉

## 待遇
月薪 NTD 80,000 - 120,000
"""


@pytest.mark.asyncio
async def test_from_url():
    print("Test 1: extract_from_url (Yourator)")
    raw_content, result = await asyncio.wait_for(extract_from_url(YOURATOR_URL), timeout=120)

    assert raw_content is not None, "Firecrawl failed"
    assert len(raw_content) > 0, "Raw content is empty"

    print(f"raw markdown length: {len(raw_content)}")

    assert result is not None, "LLM extraction failed"
    print(f"Company: {result.company}")
    print(f"Title: {result.title}")
    print(f"Skills: {result.required_skills}")
    print(f"Full JSON:\n{result.model_dump_json(indent=2)}")
    


@pytest.mark.asyncio
async def test_from_text():
    print("\nTest 2: extract_from_text (pasted JD)")
    result = await asyncio.wait_for(extract_from_text(PASTE_JD), timeout=120)

    assert result is not None, "from_text returned None"
    print(f"Company: {result.company}")
    print(f"Title: {result.title}")
    print(f"Salary: {result.salary}")
    print(f"Required years: {result.required_years}")
    