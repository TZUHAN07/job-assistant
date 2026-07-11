from typing import Optional
import logging
import instructor
from dotenv import load_dotenv
from instructor.core.exceptions import InstructorRetryException

from src.schemas import ResumeParsed

load_dotenv()

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 30000

client = instructor.from_provider(
    "google/gemini-2.5-flash",
    async_client=True,
)


async def extract_resume_structured(content_text: str) -> Optional[ResumeParsed]:
    """
    使用 Gemini + Instructor 將純文字履歷解析為結構化 Pydantic 物件。

    Returns:
        ResumeParsed: 解析成功時返回 Pydantic 模型
        None: 發生任何錯誤時返回 None，供外部路由做 Fallback 處理
    """

    if len(content_text) > MAX_CONTENT_LENGTH:
        logger.warning(
            f"Content truncated: {len(content_text)} -> {MAX_CONTENT_LENGTH}"
        )
        content_text = content_text[:MAX_CONTENT_LENGTH]

    system_instruction = (
        "你是一個專業的 AI 獵頭與履歷解析專家。\n"
        "你的唯一任務是仔細閱讀原始履歷文字，並精確地將資訊分類填入指定的 Schema 中。\n"
        "請務必使用『繁體中文』回答所有的文字、描述與摘要欄位（除了姓名、公司名等專有名詞可保持原文）。\n"
        "保持客觀，不要自行發明或虛構履歷中不存在的技能或經歷。"
    )

    user_prompt = f"這是履歷的原始文字：\n\n{content_text}\n\n請幫我提取結構化資料。"

    try:
        result: ResumeParsed = await client.create(
            response_model=ResumeParsed,  #
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=3,
        )
        logger.info(
            f"Resume extracted: name={result.name!r}, skills_count={len(result.skills)}"
        )

        return result

    except InstructorRetryException:
        logger.exception(
            f"Instructor retry exhausted. content_length={len(content_text)}"
        )
        return None

    except Exception:
        logger.exception(
            f"Gemini API unexpected error. content_length={len(content_text)}"
        )
        return None
