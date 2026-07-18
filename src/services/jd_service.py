import logging
from typing import Optional

import instructor
from instructor.core.exceptions import InstructorRetryException
from firecrawl import AsyncFirecrawl
from dotenv import load_dotenv

from src.schemas import JobParsed

load_dotenv()
logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 30000

llm_client = instructor.from_provider(
    "google/gemini-2.5-flash",
    async_client=True,
)

firecrawl = AsyncFirecrawl()


async def extract_with_llm(content_text: str) -> Optional[JobParsed]:
    """
    Private helper: Call Gemini + Instructor to extract JobParsed from raw text.
    Shared by extract_from_url and extract_from_text.
    """
     
    if len(content_text) > MAX_CONTENT_LENGTH:
        logger.warning(
            f"Content truncated: {len(content_text)} -> {MAX_CONTENT_LENGTH}"
        )
        content_text = content_text[:MAX_CONTENT_LENGTH]

    system_instruction = (
        "你是一個專業的 AI 獵頭與職缺解析專家。\n"
        "你的唯一任務是仔細閱讀原始職缺文字，並精確地將資訊分類填入指定的 Schema 中。\n"
        "請務必使用『繁體中文』回答所有的文字、描述與摘要欄位（除了公司名等專有名詞可保持原文）。\n"
        "保持客觀，不要自行發明或虛構職缺中不存在的技能或經歷。"
    )

    user_prompt = f"這是職缺的原始文字：\n\n{content_text}\n\n請幫我提取結構化資料。"

    try:
        result: JobParsed = await llm_client.create(
            response_model=JobParsed,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=3,
        )
        logger.info(
            f"Job extracted: title={result.title!r}, skills_count={len(result.required_skills)}"
        )

        return result

    except InstructorRetryException:
        logger.exception(
            f"Instructor retry exhausted. content_length={len(content_text)}"
        )
        return None

    except Exception:
        logger.exception(
            f"Failed to extract job from content. content_length={len(content_text)}"
        )
        return None


async def extract_from_url(url: str) -> Optional[JobParsed]:

    logger.info(f"Scraping JD from URL: {url}")

    try:
        response = await firecrawl.scrape(url, formats=["markdown"], wait_for=5000)

        markdown = response.markdown or ""

        if not markdown or len(markdown) < 100:
            logger.warning(f"Firecrawl  content too short ({len(markdown)} chars): {url}")
            return None

        return await extract_with_llm(markdown)

    except Exception:
        logger.exception(f"Firecrawl scraping failed for URL {url} ")
        return None


async def extract_from_text(text: str) -> Optional[JobParsed]:

    logger.info(f"Extracting JD directly from pasted text (length: {len(text)})")

    if not text.strip():
        logger.warning("Empty text received for JD extraction")
        return None

    return await extract_with_llm(text)
