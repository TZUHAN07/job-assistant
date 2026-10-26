import argparse
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone

from src.database import engine
from src.services.interview_service import (
    execute_tool,
    load_job_requirements,
    load_resume_evidence,
    run_interview,
)

from dotenv import load_dotenv
from google import genai
from google.genai import types


async def check_database(matching_id: int):
    try:
        result = await load_job_requirements(matching_id)
        print("資料庫查詢結果：")
        print(result)
    finally:
        await engine.dispose()


async def check_resume(matching_id: int):
    try:
        result = await load_resume_evidence(matching_id)
        print("履歷查詢結果：")
        print(result)
    finally:
        await engine.dispose()


async def check_tools(matching_id: int):
    try:
        tool_names = [
            "get_job_requirements",
            "get_resume_evidence",
        ]

        for name in tool_names:
            result = await execute_tool(name, {}, matching_id)

            print("工具：", name)
            print("結果欄位：", list(result.keys()))

            if "error" in result:
                raise ValueError(result["error"])
    finally:
        await engine.dispose()


def save_interview_report(artifact: dict) -> Path:

    output_dir = Path(__file__).resolve().parents[1] / "evals/interviews/local"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = output_dir / f"matching_{artifact['matching_id']}_{timestamp}.json"

    # 避免意外覆蓋已存在的報告。
    with output_path.open("x", encoding="utf-8") as file:
        json.dump(artifact, file, ensure_ascii=False, indent=2)

    return output_path


async def run_cli(client, matching_id: int):
    try:
        return await run_interview(client, matching_id, on_progress=print)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根據指定的匹配紀錄準備面試題")

    parser.add_argument(
        "--matching-id",
        type=int,
        required=True,
        help="要準備面試的匹配紀錄 ID",
    )

    parser.add_argument(
        "--check-input",
        action="store_true",
        help="只檢查輸入，不呼叫 Gemini",
    )

    parser.add_argument(
        "--check-db",
        action="store_true",
        help="只查詢職缺資料，不呼叫 Gemini",
    )

    parser.add_argument(
        "--check-resume",
        action="store_true",
        help="只查詢履歷資料，不呼叫 Gemini",
    )

    parser.add_argument(
        "--check-tools",
        action="store_true",
        help="檢查兩個工具的分派與查詢，不呼叫 Gemini",
    )

    args = parser.parse_args()

    if args.matching_id <= 0:
        parser.error("--matching-id 必須是正整數")

    matching_id = args.matching_id

    print("目前選定的匹配紀錄：", args.matching_id)

    if args.check_input:
        print("輸入格式正確，尚未查詢資料庫，也未呼叫 Gemini。")
        raise SystemExit(0)

    if args.check_db:
        try:
            asyncio.run(check_database(matching_id))
        except ValueError as error:
            print("查詢未完成：", error)
            raise SystemExit(1)

        raise SystemExit(0)

    if args.check_resume:
        try:
            asyncio.run(check_resume(matching_id))
        except ValueError as error:
            print("查詢未完成：", error)
            raise SystemExit(1)

        raise SystemExit(0)

    if args.check_tools:
        try:
            asyncio.run(check_tools(matching_id))
        except ValueError as error:
            print("查詢未完成：", error)
            raise SystemExit(1)

        raise SystemExit(0)

    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("請先在 .env 設定 Gemini API key")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000),
    )

    try:
        artifact = asyncio.run(run_cli(client, matching_id))
        output_path = save_interview_report(artifact)

        for index, question in enumerate(artifact["questions"], 1):
            print(f"\n{index}. [{question['kind']}] {question['question']}")
            print("出題理由：", question["rationale"])

        print("\n引用 ID 核對通過，語意仍須人工確認。")
        print("本機報告：", output_path)
    except ValueError as error:
        print("生成未完成：", error)
        raise SystemExit(1)
    finally:
        client.close()
