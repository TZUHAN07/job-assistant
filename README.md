# job-assistant

> AI 求職助手 — 履歷分析、JD 匹配評分、cover letter 生成。
> 為求職 dogfooding 自用，未來開放公開。

🚧 **Status**: WIP (Week 1 - Setup)

---
## 設計文件

詳細的系統規格與 API schema 請見 [`specs/`](./specs/) 資料夾。

## Tech Stack

| 類別 | 技術 |
|---|---|
| Backend | Python 3.12.2 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 |
| Database | PostgreSQL + Redis (cache) |
| AI | Anthropic Claude API（含 prompt caching） |
| Scraping | firecrawl（on-demand 單頁解析） |
| Frontend | Vanilla JS (v1) → Next.js (v2) |
| Deploy | Fly.io |
| CI/CD | GitHub Actions |

---

## Roadmap

- [ ] **Week 1**: Python refresher + FastAPI 基礎 + repo setup + auth
- [ ] **Week 2**: PDF parsing + 履歷分析 endpoint
- [ ] **Week 3**: JD on-demand 解析 + 匹配評分 + cover letter
- [ ] **Week 4**: Frontend + Deploy + 履歷更新

---

## Getting Started

> 等 Week 1 dev environment 完成後補上。

---

## Features

> 等 v1 ship 後補 demo gif。

---

## Live Demo

> 預計部署於 `job.tzuhan.dev`（Fly.io）。

---

## License

TBD
