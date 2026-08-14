"""
Compare OLD vs NEW cover letter prompts side-by-side.

Usage:
    python scripts/compare_prompts.py

Prerequisites:
    - Local Postgres running
    - .env with GEMINI_API_KEY
    - At least 1 matching in DB (with resume + job parsed)
"""

import asyncio
import statistics
from typing import List

import instructor
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models import Matching
from src.schemas import CoverLetterResult, ResumeParsed, JobParsed, MatchingResult

load_dotenv()

# ═══════════════════════════════════════════════════════════
# OLD PROMPT (from git history — paste old SYSTEM_INSTRUCTION)
# ═══════════════════════════════════════════════════════════
OLD_SYSTEM = """你是專業的求職顧問, 專精於撰寫台灣科技業求職信 (Cover Letter).

【你的任務】
根據候選人履歷 (Resume)、目標職缺 (JD)、與匹配分析 (Matching Result),
以及先前計算出的「匹配分析結果」，為求職者撰寫一份極具吸引力、客製化且真誠的求職信。

【求職信結構 (4 段)】
1. Opening (開場)：簡潔說明「我為何寫這封信」+「對職缺的興趣」
2. Why Me (為何是我)：從 matching.matched_skills 挑 2-3 個核心技能,
   結合 Resume 具體專案經驗展示能力
3. Why Fit (為何合這公司)：展現對公司/職位的理解, 說明如何貢獻
4. Call to Action (行動呼籲)：邀請面試, 表達期待

【收件人稱謂 Fallback】
- 若職缺資訊中有明確公司名, 使用「[公司名] 招募團隊 您好」
- 若職缺資訊缺公司名 or 是空字串 or "未知公司", 統一改用「招募團隊 您好」

【tone 控制】
- professional: 真誠、專業、正式、有信心

【具體證據導向】
- 善用 MatchingResult 中的 match_reasons 與 matched_skills
- 舉例時必須提及具體的專案經驗

【語言】
- 使用台灣繁體中文
- 專有名詞保留原文

【防幻覺】
- 嚴格基於 Resume 提到的技能與經驗
- 不誇大匹配度

【格式】
- Content 完整信件文字, 直接可 copy 貼到 email

【聯繫資訊】
- 若 Resume 內有 github_url, 必須附上
"""

from src.services.cover_letter_service import SYSTEM_INSTRUCTION as NEW_SYSTEM

FORBIDDEN_WORDS = ["精通", "Expert", "資深", "多年", "高併發", "大規模", "enterprise-scale"]

def evaluate_letter(letter: CoverLetterResult) -> dict:
    """Score letter against 6 criteria."""
    length = len(letter.full_content)
    forbidden_count = sum(1 for w in FORBIDDEN_WORDS if w in letter.full_content)

    evidence_keywords = [
        "job-assistant", "ig-clone", "FastAPI", "Gemini", "Instructor",
        "Docker", "AWS", "Socket.io", "GitHub Actions", "PostgreSQL",
        "Node.js", "Python", "MongoDB", "SQLAlchemy", "Cloudflare",
    ]
    evidence_count = sum(1 for k in evidence_keywords if k in letter.full_content)

    return {
        "length": length,
        "length_compliant": 350 <= length <= 500,
        "forbidden_count": forbidden_count,
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
        print(f"  [OLD #{i+1}] length={score['length']}, evidence={score['evidence_count']}, forbidden={score['forbidden_count']}")

    print(f"\n{'='*60}")
    print(f"Generating {N} letters with NEW prompt...")
    print(f"{'='*60}")
    for i in range(N):
        letter = await generate_with_prompt(client, NEW_SYSTEM, user_prompt)
        score = evaluate_letter(letter)
        new_scores.append(score)
        print(f"  [NEW #{i+1}] length={score['length']}, evidence={score['evidence_count']}, forbidden={score['forbidden_count']}")

    print(f"\n{'='*60}")
    print("📊 COMPARISON SUMMARY")
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
