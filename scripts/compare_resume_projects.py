"""離線比較兩次履歷解析；不呼叫 LLM、不修改資料庫。"""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def compact(value):
    return "".join(value.split()).casefold()


def inspect_run(run, source, expected):
    projects = run["parsed_data"].get("projects", [])
    rows = []
    for name, technologies in expected.items():
        matches = [p for p in projects if compact(p["name"]).split("—")[0] == compact(name)]
        if len(matches) != 1:
            rows.append({"project": name, "status": "missing" if not matches else "ambiguous"})
            continue
        project = matches[0]
        actual = {compact(t) for t in project.get("technologies", [])}
        quotes = project.get("source_quotes", [])
        rows.append({
            "project": name, "status": "found", "context": project.get("context"),
            "implementation_count": len(project.get("implementations", [])),
            "technologies": project.get("technologies", []),
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
    expected = load(args.expectations)["expected_projects"]
    report = {
        "resume_id": snapshot["resume"]["id"], "same_input": True,
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
