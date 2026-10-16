"""本機求職信審查；預設離線驗證，--review 才呼叫付費 API。"""
import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.schemas import ResumeParsed, JobParsed, CoverLetterResult
from src.services.cover_letter_review_service import build_evidence, review_cover_letter, MODEL


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="preview_cover_letter.py 產生的 JSON")
    parser.add_argument("--review", action="store_true")
    args = parser.parse_args()
    raw = args.input.read_bytes()
    data = json.loads(raw)
    resume = ResumeParsed.model_validate(data["inputs"]["resume"])
    job = JobParsed.model_validate(data["inputs"]["job"])
    letter = CoverLetterResult.model_validate(data["result"])
    evidence = build_evidence(resume, job)
    print(f"輸入驗證通過；可供核對的證據欄位：{len(evidence)}")
    if not args.review:
        print("未呼叫 AI。加 --review 才執行付費檢查。")
        return
    print("正在檢查，上限 90 秒，未設定自動重試…", flush=True)
    review = await review_cover_letter(resume, job, letter)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "evals/cover_letters/local"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"cover_letter_review_{stamp}"
    report = {
        "input_file": args.input.name, "input_sha256": hashlib.sha256(raw).hexdigest(),
        "model": MODEL, "review": review.model_dump(), "evidence": evidence,
        "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in [
            "src/schemas/cover_letter_review.py", "src/services/cover_letter_review_service.py"]},
        "human_review_required": True,
    }
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 求職信檢查結果", f"狀態：{review.status}",
             "模型判斷需人工確認；no_issues_found 不是事實保證。未修改原信。"]
    if review.error:
        lines.append(review.error)
    for index, issue in enumerate(review.issues, 1):
        lines += [f"\n## 問題 {index}：{issue.category}", f"欄位：{issue.field}",
                  f"原句：{issue.quote}", f"理由：{issue.reason}",
                  f"建議：{issue.suggested_revision}", "相關證據："]
        lines += [f"- {key}：{evidence[key]}" for key in issue.evidence_ids] or ["- 無相關引用；仍需人工確認。"]
    output.with_suffix(".md").write_text("\n\n".join(lines) + "\n")
    print(f"狀態：{review.status}；問題數：{len(review.issues)}")
    print(f"閱讀報告：{output.with_suffix('.md')}")
    if review.status == "review_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
