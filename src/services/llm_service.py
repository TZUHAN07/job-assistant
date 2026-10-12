from typing import Optional
import logging
import instructor
from dotenv import load_dotenv
from instructor.core.exceptions import InstructorRetryException

from src.schemas import ResumeParsed
from src.services.resume_evidence import validate_project_quotes

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
        "保持客觀，不要自行發明或虛構履歷中不存在的技能或經歷。\n"
        "逐一保留履歷中具體描述的專案於 projects，不可只把專案名稱放入 summary 或技術放入 skills。\n"
        "experience 保存工作經歷；個人及課程專案不可冒充正式任職經驗。\n"
        "專案 context 依明確標題或敘述分類，沒有證據就填 unknown。\n"
        "implementations 保留做過的功能與動作；不要把部署推論成完整維運、測試推論成穩定性保證。\n"
        "technologies 只收錄與該專案有明確關聯的技術，不從全域技能清單猜測。\n"
        "一般欄位（含 name、implementations、summary）使用正常可讀文字，修復 PDF 字元間的多餘空白，例如 F a s t A P I 寫成 FastAPI；英文詞間保留正常空格。\n"
        "需查看履歷全部段落：若摘要明確寫某專案使用某技術，也應納入該專案，並引用該段；不可僅依技術名稱相鄰就推論歸屬。\n"
        "source_quotes 是繁中重述規則的例外：必須從輸入逐字摘錄，保留原語言、空白與換行。\n"
        "摘要與技能描述也不得提高原文的經驗強度，不把 LLM API 整合寫成 AI coding workflow。"
    )

    user_prompt = f"這是履歷的原始文字：\n\n{content_text}\n\n請幫我提取結構化資料。"

    try:
        result: ResumeParsed = await client.create(
            response_model=ResumeParsed,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=3,
        )
        result = validate_project_quotes(result, content_text)
        logger.info(
            f"Resume extracted: name={result.name!r}, skills_count={len(result.skills)}"
        )

        return result

    except ValueError:
        logger.warning("Resume evidence validation failed; extracted result rejected")
        return None

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
