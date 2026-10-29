"""面試生成的本機用量紀錄；不保存提示、回答或例外訊息。"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

logger = logging.getLogger(__name__)
USAGE_DIR = Path(__file__).resolve().parents[2] / "logs" / "interview_usage"
TOKEN_FIELDS = (
    "prompt_token_count", "candidates_token_count", "thoughts_token_count",
    "cached_content_token_count", "tool_use_prompt_token_count", "total_token_count",
)


class InterviewUsage:
    def __init__(self, matching_id):
        self.started = perf_counter()
        self.record = {
            "run_id": uuid4().hex,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "matching_id": matching_id,
            "model": "gemini-2.5-flash",
            "status": "running",
            "rounds": [],
        }

    async def generate(self, client, **kwargs):
        started = perf_counter()
        row = {"round": len(self.record["rounds"]) + 1,
               "status": "failed", "error_type": None,
               **{field: None for field in TOKEN_FIELDS}}
        self.record["rounds"].append(row)
        try:
            response = await asyncio.to_thread(client.models.generate_content, **kwargs)
            metadata = getattr(response, "usage_metadata", None)
            for field in TOKEN_FIELDS:
                value = getattr(metadata, field, None)
                row[field] = value if type(value) is int and value >= 0 else None
            row["status"] = "response_received"
            return response
        except BaseException as exc:
            row["error_type"] = type(exc).__name__
            if isinstance(exc, asyncio.CancelledError):
                row["status"] = "cancelled"
            raise
        finally:
            row["duration_ms"] = round((perf_counter() - started) * 1000, 2)

    def finish(self, status, error_type=None):
        self.record.update(status=status, error_type=error_type,
                           duration_ms=round((perf_counter() - self.started) * 1000, 2))
        totals = {}
        for field in TOKEN_FIELDS:
            values = [row[field] for row in self.record["rounds"]]
            # 任一輪未知時，不能把已知部分當成完整用量。
            totals[field] = sum(values) if values and all(v is not None for v in values) else None
        self.record["totals"] = totals
        try:
            USAGE_DIR.mkdir(parents=True, exist_ok=True)
            with (USAGE_DIR / f"{self.record['run_id']}.json").open("x", encoding="utf-8") as output:
                json.dump(self.record, output, ensure_ascii=False, indent=2)
        except OSError as exc:
            # 觀測功能不能讓已生成的題目失敗，也不能遮蔽原本的例外。
            logger.warning("Interview usage write failed: %s", type(exc).__name__)
