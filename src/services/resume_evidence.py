"""核對來源文字；只驗證引用存在，不代表引用支持所有專案主張。"""
from src.schemas import ResumeParsed


def restore_source_quote(source: str, quote: str) -> str:
    if not quote.strip():
        raise ValueError("Empty project source quote")
    if quote in source:
        return quote

    # 保留位置對照，忽略空白比對後取回原文；不修改大小寫或標點。
    positions = [i for i, char in enumerate(source) if not char.isspace()]
    compact_source = "".join(source[i] for i in positions)
    compact_quote = "".join(quote.split())
    start = compact_source.find(compact_quote)
    if start < 0:
        raise ValueError("Project source quote not found in resume")
    return source[positions[start]:positions[start + len(compact_quote) - 1] + 1]


def validate_project_quotes(resume: ResumeParsed, source: str) -> ResumeParsed:
    # 全部通過才回傳新物件，避免失敗時留下部分已修改的解析結果。
    checked = resume.model_copy(deep=True)
    for project in checked.projects:
        project.source_quotes = [restore_source_quote(source, quote) for quote in project.source_quotes]
    return checked
