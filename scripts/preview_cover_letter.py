"""固定本機輸入的求職信 MVP 驗證；預設只檢查，--generate 才呼叫 Gemini。"""
import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.schemas import ResumeParsed, JobParsed, MatchingResult


def read(path):
    return json.loads(path.read_text())


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--resume', type=Path, required=True)
    parser.add_argument('--generate', action='store_true', help='實際呼叫 Gemini，會產生 API 費用')
    args = parser.parse_args()
    snapshot, run = read(args.snapshot), read(args.resume)
    raw_hash = hashlib.sha256(snapshot['resume']['content_text'].encode()).hexdigest()
    if run.get('resume_id') != snapshot['resume']['id'] or run.get('input_sha256') != raw_hash:
        parser.error('新版履歷與快照的 ID 或原文 hash 不一致')
    letter, match = snapshot['letter'], snapshot['matching']
    if (letter['matching_id'] != match['id'] or match['resume_id'] != run['resume_id']
            or match['job_id'] != snapshot['job']['id']):
        parser.error('信件、Matching、履歷與 JD 關聯不符')
    resume = ResumeParsed.model_validate(run['parsed_data'])
    job = JobParsed.model_validate(snapshot['job']['parsed_data'])
    matching = MatchingResult.model_validate({
        key: match[key] for key in MatchingResult.model_fields if match.get(key) is not None
    })
    tone, language = letter['tone'], letter['language']
    print(f"輸入通過：履歷 {run['resume_id']}，Matching {match['id']}，原信 {letter['id']} / v{letter['version']}，{len(resume.projects)} 個專案")
    print(f'沿用語氣 {tone}、語言 {language}；不修改資料庫。')
    if not args.generate:
        print('僅驗證輸入，未呼叫 AI。加上 --generate 才生成。')
        return
    from src.services import cover_letter_service as service
    original_create = service.llm_client.create

    async def single_attempt(**kwargs):
        # 僅本次 CLI 關閉 Instructor 自動重試，不改動網站預設行為。
        kwargs['max_retries'] = 1
        return await original_create(**kwargs)

    print('開始呼叫 Gemini（Instructor 單次嘗試，上限 120 秒）…', flush=True)
    try:
        with patch.object(service.llm_client, 'create', single_attempt):
            result = await asyncio.wait_for(service.generate_cover_letter(
                resume, job, matching, tone=tone, language=language,
            ), timeout=120)
    except TimeoutError:
        raise SystemExit('等待逾時；未自動重試。供應商可能仍處理請求或計費。')
    if result is None:
        raise SystemExit('生成失敗；未自動重試，未寫入成功結果。')
    timestamp = datetime.now(timezone.utc)
    folder = ROOT / 'evals/cover_letters/local'
    folder.mkdir(parents=True, exist_ok=True)
    name = f"letter_{letter['id']}_preview_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}"
    payload = {
        'created_at': timestamp.isoformat(), 'baseline_letter_id': letter['id'],
        'historical_prompt_verified': False,
        'model': 'google/gemini-2.5-flash', 'tone': tone, 'language': language,
        'input_sha256': raw_hash,
        'inputs': {'resume': resume.model_dump(), 'job': job.model_dump(), 'matching': matching.model_dump()},
        'source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
            'src/services/cover_letter_service.py', 'src/schemas/cover_letter_result.py')},
        'baseline_content': letter['content'], 'result': result.model_dump(),
    }
    json_path, md_path = folder / f'{name}.json', folder / f'{name}.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    md_path.write_text(f'''# Case 2 求職信比較

本次使用目前 service；原信當時的 prompt 版本未知，不能宣稱只更換履歷這一個變因。
單次結果不代表穩定改善。以下由使用者人工審核，尚無自動評分。

- [ ] 沒有宣稱建立過 AI coding workflow
- [ ] 沒有將個人專案誇大為商業經驗或完整維運能力
- [ ] 描述的具體實作可回到履歷驗證

## 原信 {letter['id']} / v{letter['version']}

{letter['content']}

## 本次生成

主旨：{result.title}

{result.full_content}
''')
    print(f'JSON：{json_path}\n閱讀比較：{md_path}')


if __name__ == '__main__':
    asyncio.run(main())
