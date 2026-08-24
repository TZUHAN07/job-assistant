"""
Compare OLD vs NEW cover letter prompts side-by-side.

Usage (from project root):
    PYTHONPATH=. python scripts/compare_prompts.py
    # or
    python -m scripts.compare_prompts

Prerequisites:
    - Local Postgres running
    - .env with GEMINI_API_KEY
    - At least 1 matching in DB (with resume + job parsed)
"""

import asyncio
import statistics
import sys
from pathlib import Path

# 允許直接執行 (python scripts/compare_prompts.py) 找到 src/ module
# 若用 python -m scripts.compare_prompts 則不需要此 hack
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import instructor
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models import Matching
from src.schemas import CoverLetterResult, ResumeParsed, JobParsed, MatchingResult

load_dotenv()

# ═══════════════════════════════════════════════════════════
# OLD PROMPT — V2 baseline (通用行業版, 加了【職種適配】+【避免 AI 求職信腔】
# 但沒有 Requirement Mirroring / No Skill Inference / Contribution Accuracy /
# No Unsupported Outcome Claims / Why Company Accuracy)
# ═══════════════════════════════════════════════════════════
OLD_SYSTEM = """你是熟悉台灣求職市場與各產業招募標準的專業求職信顧問。

你的任務是根據 Resume、Job Description 與 Matching Result，
撰寫一封「短、具體、有證據、可直接寄出」的客製化求職信。

候選人可能來自不同職種，例如：
Engineering、AI、Data、Product、Design、Marketing、Sales、Education、Finance、Healthcare 等。

你必須根據 Resume 與 Job 自動判斷候選人的背景與目標職位，
採用符合該職種的招募語言與 evidence。
不要假設候選人一定是工程師。


【核心原則】

1. 所有候選人資訊必須來自 Resume。
2. 所有職缺需求必須來自 Job。
3. Matching Result 只作為「相關性提示」，不能創造 Resume 中不存在的經驗。
4. 優先使用具體的「行動 → 技能/方法 → 成果」作為證據。
5. 不虛構工作年資、公司、職稱、技術、KPI、用戶規模、營收或成果。
6. 不把 portfolio project 描述成正式工作經驗。
7. 沒有 evidence 時，不要自行補充。
8. 不要為了符合 JD 而假設候選人具備 Resume 沒有的技能。
9. 求職信應該呈現「為什麼這位候選人適合這個職位」，
   而不是重新複述整份履歷。


【職種適配】

根據 Resume + Job 自動選擇最相關的 evidence。

例如：

Engineering：
→ 技術、系統、架構、API、測試、部署、效能、debugging、project implementation

AI / Data：
→ 模型、資料處理、LLM、分析方法、實驗、automation、data-driven decision

Product / PM：
→ product ownership、需求分析、stakeholder communication、產品成果、優先級決策

Design：
→ design process、user research、prototype、design system、user experience、portfolio evidence

Marketing：
→ campaign、acquisition、conversion、ROI/ROAS、A/B testing、audience analysis

Sales：
→ client development、pipeline、conversion、revenue、relationship management

Education：
→ curriculum、teaching、learning outcomes、communication、problem solving

其他職種：
→ 根據 Resume 與 Job 中實際出現的技能與成果選擇 evidence。

禁止將其他職種硬套成工程師語言。


【Evidence-based】

優先使用 Matching Result 中的：

- match_reasons
- matched_skills

但所有具體 evidence 必須回到 Resume 驗證。

Evidence 優先順序：

1. 具體成果 / KPI
2. 實際完成的專案
3. 使用的工具 / 技術 / 方法
4. 工作中的具體責任
5. 教育 / 訓練背景

避免只有形容詞。

GOOD：
「使用 Google Analytics 與 A/B Testing 分析使用者行為，並調整廣告受眾與文案，使轉換率提升至近 10%。」

BAD：
「我具備優秀的數據分析能力，能為公司創造價值。」


【JD Matching】

優先選擇 Resume 與 Job 的「實際交集」。

使用：

JD Requirement
→ Candidate Evidence
→ Potential Contribution

如果某項 JD requirement 在 Resume 沒有直接證據，不要假裝具備。

不要主動強調 Missing Skills。


【Career Switcher / Junior Accuracy】

如果 Resume 顯示候選人屬於 Junior 或 Career Switcher：

- 使用 project experience / hands-on experience
- 不使用 professional experience / years of experience，除非 Resume 明確支持
- 個人專案不得描述成正式商業工作經驗
- 訓練營不得描述成正式工作經驗

禁止無 evidence 的描述：
「精通」「Expert」「Senior」「資深」「多年經驗」「高併發」「大規模」「enterprise-scale」


【避免 AI 求職信腔】

避免過度使用：
「充滿熱情」「深感興趣」「高度契合」「實質貢獻」「全面能力」
「展現決心」「我深信」「我相信自己能」「前瞻性的」「有影響力的」「非常期待」

優先使用具體事實與職缺需求。


【輸出結構】

title：15–25 字，格式：「應徵 [職位]｜[姓名]」
opening：2–3 句
why_me：3–4 句，建立「JD → Evidence → Contribution」連結
why_company：2–3 句
call_to_action：1–2 句
full_content：zh-TW 350–500 字 / en-US 250–350 words


【Recipient】

若 Job 有明確公司名稱：「[公司名稱] 招募團隊 您好」
若公司名稱缺失、空字串或為「未知公司」：「招募團隊 您好」


【Contact】

Resume 有 github_url → Call to Action 加入
Resume 有 linkedin_url → 加入
兩者皆無 → 不虛構
"""

from src.services.cover_letter_service import SYSTEM_INSTRUCTION as NEW_SYSTEM

# Forbidden words split by category (easier to see violation type)
FORBIDDEN_CATEGORIES = {
    "誇大形容詞": ["精通", "Expert", "資深", "多年", "高併發", "大規模", "enterprise-scale"],
    "AI-tone 空泛熱情": ["充滿熱情", "深感興趣", "深信", "相信自己能", "非常期待"],
    "AI-tone 陳腔契合": ["不謀而合", "高度契合", "理念一致", "願景相符"],
    "空泛未來承諾": ["將達成", "能為公司創造", "顯著貢獻", "實質效益", "帶來顯著價值"],
    "空泛公司評價": ["前瞻性的", "有影響力的", "市場發展潛力", "創新的領導者"],
    "老派用語": ["本人", "敝人", "承蒙貴公司", "懇請貴公司"],
}

FORBIDDEN_WORDS = [w for words in FORBIDDEN_CATEGORIES.values() for w in words]


def evaluate_letter(letter: CoverLetterResult) -> dict:
    """Score letter against 6 criteria + per-category forbidden breakdown."""
    length = len(letter.full_content)

    # Total forbidden count
    forbidden_count = sum(1 for w in FORBIDDEN_WORDS if w in letter.full_content)

    # Per-category breakdown (see which type of violation)
    forbidden_by_category = {
        cat: [w for w in words if w in letter.full_content]
        for cat, words in FORBIDDEN_CATEGORIES.items()
    }
    forbidden_categories_hit = {
        cat: len(hits) for cat, hits in forbidden_by_category.items() if hits
    }

    evidence_keywords = [
        # Tech
        "job-assistant", "ig-clone", "FastAPI", "Gemini", "Instructor",
        "Docker", "AWS", "Socket.io", "GitHub Actions", "PostgreSQL",
        "Node.js", "Python", "MongoDB", "SQLAlchemy", "Cloudflare",
        # Design
        "Figma", "Design System", "User Flow", "Prototype", "User Research",
        # Marketing
        "GA4", "Google Ads", "Meta Ads", "ROAS", "A/B", "CTR", "CPA",
        # Product / PM
        "Roadmap", "PRD", "User Story", "Sprint", "Mixpanel", "Looker",
    ]
    evidence_count = sum(1 for k in evidence_keywords if k in letter.full_content)

    return {
        "length": length,
        "length_compliant": 380 <= length <= 480,  # narrower target
        "forbidden_count": forbidden_count,
        "forbidden_by_category": forbidden_categories_hit,
        "no_forbidden": forbidden_count == 0,
        "evidence_count": evidence_count,
        "high_evidence": evidence_count >= 3,
        "structure_complete": all([
            letter.title, letter.opening, letter.why_me,
            letter.why_company, letter.call_to_action, letter.full_content,
        ]),
    }


async def generate_with_prompt(client, system_prompt: str, user_prompt: str) -> CoverLetterResult:
    return await client.create(
        response_model=CoverLetterResult,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_retries=2,
    )


async def main():
    async for db in get_db():
        result = await db.execute(
            select(Matching)
            .where(Matching.processed_at.is_not(None))
            .options(selectinload(Matching.resume), selectinload(Matching.job))
            .limit(1)
        )
        matching_row = result.scalar_one_or_none()
        break

    if not matching_row:
        print("❌ No matching found in DB. Run POST /matchings/score first.")
        return

    resume = ResumeParsed(**matching_row.resume.parsed_data)
    job = JobParsed(**matching_row.job.parsed_data)
    matching = MatchingResult(
        match_reasons=matching_row.match_reasons or [],
        matched_skills=matching_row.matched_skills or [],
        missing_skills=matching_row.missing_skills or [],
        quick_wins=matching_row.quick_wins or [],
        long_term_goals=matching_row.long_term_goals or [],
        score=matching_row.score or 0,
    )

    user_prompt = f"""請根據以下 Resume、Job 與 Matching Result，撰寫 professional 語氣的求職信。

【指定語言】zh-TW

=== Resume ===
{resume.model_dump_json(indent=2)}

=== Job ===
{job.model_dump_json(indent=2)}

=== Matching Result ===
Score: {matching.score}/100
Match Reasons: {matching.match_reasons}
Matched Skills: {matching.matched_skills}
Missing Skills: {matching.missing_skills}
"""

    client = instructor.from_provider("google/gemini-2.5-flash", async_client=True)

    N = 3
    old_scores = []
    new_scores = []

    print(f"\n{'='*60}")
    print(f"Generating {N} letters with OLD prompt...")
    print(f"{'='*60}")
    for i in range(N):
        letter = await generate_with_prompt(client, OLD_SYSTEM, user_prompt)
        score = evaluate_letter(letter)
        old_scores.append(score)
        cat_str = ", ".join(f"{c}:{n}" for c, n in score["forbidden_by_category"].items()) or "-"
        print(f"  [OLD #{i+1}] len={score['length']:>3} ev={score['evidence_count']} forbid={score['forbidden_count']} ({cat_str})")

    print(f"\n{'='*60}")
    print(f"Generating {N} letters with NEW prompt...")
    print(f"{'='*60}")
    for i in range(N):
        letter = await generate_with_prompt(client, NEW_SYSTEM, user_prompt)
        score = evaluate_letter(letter)
        new_scores.append(score)
        cat_str = ", ".join(f"{c}:{n}" for c, n in score["forbidden_by_category"].items()) or "-"
        print(f"  [NEW #{i+1}] len={score['length']:>3} ev={score['evidence_count']} forbid={score['forbidden_count']} ({cat_str})")

    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")

    def summary(scores, label):
        lengths = [s["length"] for s in scores]
        compliance = sum(s["length_compliant"] for s in scores) / len(scores)
        evidence_avg = statistics.mean(s["evidence_count"] for s in scores)
        forbidden_avg = statistics.mean(s["forbidden_count"] for s in scores)
        no_forbidden = sum(s["no_forbidden"] for s in scores) / len(scores)

        print(f"\n{label}:")
        print(f"  Length avg:              {statistics.mean(lengths):.0f} chars (target 350-500)")
        print(f"  Length compliance rate:  {compliance:.0%}")
        print(f"  Evidence density avg:    {evidence_avg:.1f} specific mentions")
        print(f"  Forbidden words avg:     {forbidden_avg:.1f} per letter")
        print(f"  Zero-hallucination rate: {no_forbidden:.0%}")

    summary(old_scores, "OLD PROMPT")
    summary(new_scores, "NEW PROMPT")
    print()


if __name__ == "__main__":
    asyncio.run(main())
