"""離線比較兩次履歷解析；不呼叫 LLM、不修改資料庫。"""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def compact(value):
    return "".join(value.split()).casefold()


def validate_expectations(expected, source):
    """先驗證評分依據，避免把沒有原文支持的期望算成模型遺漏。"""
    source_without_spaces = "".join(source.split())
    if not isinstance(expected, dict) or not expected:
        raise ValueError("expected_projects 必須是非空物件")
    for name, entries in expected.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(entries, list) or not entries:
            raise ValueError("專案名稱與預期項目不可為空")
        for entry in entries:
            if not isinstance(entry, dict) or any(
                not isinstance(entry.get(key), str) or not entry[key].strip()
                for key in ("technology", "evidence_location", "evidence_quote")
            ):
                raise ValueError(f"{name}: 每項技術需要名稱、證據位置與原句")
            quote = "".join(entry["evidence_quote"].split())
            if quote not in source_without_spaces:
                raise ValueError(f"{name}: {entry['technology']} 的證據不在原文，停止比較")
            # 此版接受專案與技術均明確出現在同段引文的標註；共現不等於語意證明。
            if compact(name) not in compact(quote) or compact(entry["technology"]) not in compact(quote):
                raise ValueError(f"{name}: 引文未明確包含專案名與技術名，需人工審核")


def inspect_run(run, source, expected):
    projects = run["parsed_data"].get("projects", [])
    rows = []
    for name, entries in expected.items():
        technologies = [entry["technology"] for entry in entries]
        matches = [p for p in projects if compact(p["name"]).split("—")[0] == compact(name)]
        if len(matches) != 1:
            rows.append({"project": name, "status": "missing" if not matches else "ambiguous", "expectation_evidence": entries})
            continue
        project = matches[0]
        actual = {compact(t) for t in project.get("technologies", [])}
        quotes = project.get("source_quotes", [])
        rows.append({
            "project": name, "status": "found", "context": project.get("context"),
            "implementation_count": len(project.get("implementations", [])),
            "technologies": project.get("technologies", []),
            "expectation_evidence": entries,
            "missing_expected_technologies": [t for t in technologies if compact(t) not in actual],
            "quote_count": len(quotes),
            "exact_quotes": sum(bool(q.strip()) and q in source for q in quotes),
            "whitespace_equivalent_quotes": sum(bool(q.strip()) and "".join(q.split()) in "".join(source.split()) for q in quotes),
        })
    return {"project_count": len(projects), "checks": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="包含 resume.content_text 的本機快照")
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--expectations", required=True)
    parser.add_argument("--output", required=True, help="建議輸出至 Git 忽略的 local/；報告可能包含私人資訊")
    args = parser.parse_args()
    snapshot, before, after = load(args.source), load(args.before), load(args.after)
    source = snapshot["resume"]["content_text"]
    digest = hashlib.sha256(source.encode()).hexdigest()
    for label, run in [("before", before), ("after", after)]:
        if run.get("input_sha256") != digest or run.get("resume_id") != snapshot["resume"]["id"]:
            parser.error(f"{label}: 履歷 ID 或輸入 hash 不一致，停止比較")
    expectations = load(args.expectations)
    if expectations.get("schema_version") != "2.0" or expectations.get("resume_id") != snapshot["resume"]["id"]:
        parser.error("預期清單版本或履歷 ID 不符")
    expected = expectations.get("expected_projects")
    try:
        validate_expectations(expected, source)
    except ValueError as error:
        parser.error(str(error))
    report = {
        "resume_id": snapshot["resume"]["id"], "same_input": True, "expectation_source_check": "passed_ignoring_whitespace",
        "before_file": Path(args.before).name, "after_file": Path(args.after).name,
        "before": inspect_run(before, source, expected),
        "after": inspect_run(after, source, expected),
        "limitations": [
            "不同次生成，不是同一次回覆的驗證前後；單次結果不能證明穩定改善。",
            "after 可能已由程式還原引用，逐字吻合不代表模型原始輸出逐字吻合。",
            "技術名稱只忽略大小寫及空白，不處理別名；預期項目是人工選定的局部檢查。",
            "引用存在不代表主張被支持；可讀性、誇大與專案歸屬仍需人工審核。",
        ],
    }
    output = Path(args.output)
    if output.resolve() in {Path(p).resolve() for p in [args.source, args.before, args.after, args.expectations]}:
        parser.error("輸出不可覆蓋輸入檔案")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("預期證據：已核對原文（只忽略空白；位置與語意關聯由人工確認）")
    for name, entries in expected.items():
        for entry in entries:
            print(f"  {name} / {entry['technology']}｜{entry['evidence_location']}：{entry['evidence_quote']}")
    for label in ["before", "after"]:
        print(f"{label}: {report[label]['project_count']} 個專案")
        for row in report[label]["checks"]:
            print(f"  {row['project']}: {row['status']}")
            if row["status"] == "found":
                print(f"    原文引用 {row['exact_quotes']}/{row['quote_count']}；忽略空白 {row['whitespace_equivalent_quotes']}/{row['quote_count']}")
                print(f"    預期技術遺漏：{', '.join(row['missing_expected_technologies']) or '無'}")
    print(f"報告：{output}")


if __name__ == "__main__":
    main()
