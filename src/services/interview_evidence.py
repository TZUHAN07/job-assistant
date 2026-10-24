from src.schemas.interview import InterviewQuestionSet


def build_evidence_catalog(job: dict, resume: dict) -> dict:
    """ID 只對應本次快照；來源順序變更後不可沿用舊 ID。"""
    catalog = {"job": {}, "resume": {}}
    for index, text in enumerate(job.get("requirements") or []):
        if text and text.strip():
            catalog["job"][f"job:{job['job_id']}:skill:{index}"] = {"text": text}
    if job.get("job_description"):
        catalog["job"][f"job:{job['job_id']}:description"] = {
            "text": job["job_description"]
        }
    for index, project in enumerate(resume.get("projects") or []):
        for quote_index, text in enumerate(project.get("source_quotes") or []):
            if text and text.strip():
                key = f"resume:{resume['resume_id']}:project:{index}:quote:{quote_index}"
                catalog["resume"][key] = {"project": project["name"], "text": text}
    return catalog


def resolve_questions(result: InterviewQuestionSet, catalog: dict) -> list[dict]:
    """只驗證引用存在，不代表已證明題目與證據的語意關聯。"""
    resolved = []
    seen = set()
    for question in result.questions:
        normalized = "".join(question.question.split())
        if not normalized or normalized in seen or not question.rationale.strip():
            raise ValueError("面試題不可空白、重複，且須提供出題理由")
        seen.add(normalized)
        if question.kind == "project_experience" and not question.resume_evidence_ids:
            raise ValueError("專案經驗題必須引用履歷證據")
        item = question.model_dump()
        for source in ("job", "resume"):
            ids = item[f"{source}_evidence_ids"]
            if len(ids) != len(set(ids)):
                raise ValueError("同一題不可重複引用相同證據 ID")
            if any(key not in catalog[source] for key in ids):
                raise ValueError(f"面試題引用不存在的 {source} 證據 ID")
            
            item[f"{source}_evidence"] = [
                {"id": key, **catalog[source][key]} for key in ids
            ]
        resolved.append(item)
    return resolved
