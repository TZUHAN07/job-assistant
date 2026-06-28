# 00 - Problem Statement

## 一句話

給求職者一個 AI-powered job search copilot，協助解析職缺需求、評估技能匹配度、生成投遞素材，並追蹤整體求職流程。

---

## 服務對象

- **v1（MVP）**：作者本人 dogfooding（待業中 junior 軟體工程師）
- **v2**：開放朋友 → 公開
  - Schema 已預留 multi-user（每張表都有 `user_id`）
  - v2 主要工作：onboarding、quota / billing、隱私升級

---

## 核心痛點（按優先序）

1. **JD 看到眼花**：每天上百個職缺，不知道哪個值得認真看
2. **匹配度判斷靠目測**：自己一個一個比對技能 vs JD，慢且不準
3. **投遞耗時**：cover letter 每家重寫，重複勞動
4. **投遞紀錄分散**：誰已投、誰已回、誰要追，記不住

---

## 核心功能（MVP）

| # | 功能 | 描述 |
|---|---|---|
| 1 | JD 解析 | 貼上 JD URL → 系統擷取並結構化職缺內容（支援 on-demand parsing）|
| 2 | 履歷分析 | 上傳 PDF / 文字履歷 → LLM 抽取結構化 + 給優缺評分 |
| 3 | 匹配評分 | JD ↔ 履歷對齊 → 0-100 分 + 缺口 keyword + 投不投建議 |
| 4 | Cover Letter 生成 | 根據 JD + 履歷生成 → 可重用、可微調、版本管理 |
| 5 | 投遞 Tracker | 公司 / 職位 / 狀態 / 備註 CRUD |

---

## 核心差異化

與一般履歷生成工具不同，本系統聚焦在「投遞決策前」的判斷流程：

- 值不值得投？
- 哪些 gap 可補？
- 哪些 keyword 必須改？
- 是否符合目標薪資與技術成長路線？

本質上是一個 decision-support system，而不是單純內容生成工具。

## 成功指標

### 性能
- JD URL → 匹配度報告 < 30 秒
- LLM 平均 token cost < $0.05 / 次分析

### 品質
- 匹配度 ≥ 60% 的職缺中，實際投遞比例 ≥ 50%
- 同 JD 連測 5 次，評分差 ≤ ±10%

### 成效
- 使用工具輔助投遞後，提升 JD 篩選效率 ≥ 50%
- 累積分析 ≥ 50 個 JD
- 產出 ≥ 20 封客製化 Cover Letters
- 獲得 ≥ 3 次面試邀約

---

## 已知風險

- LLM 匹配分數可能存在波動性與 hallucination
- 不同平台 JD HTML 結構不穩定，可能影響解析品質
- 履歷抽取品質依 PDF 格式品質而異
- Cover letter 生成可能過度模板化，需人工調整

## 不做（v1 邊界）

- ❌ 自動投遞（違反 LinkedIn / 104 / Yourator ToS）
- ❌ 定期排程爬蟲 / 批次抓取（單次 on-demand 解析 OK，cron 不做）
- ❌ 面試模擬語音對話（v3 再說）
- ❌ Mobile responsive（desktop only）
- ❌ Payment / SaaS billing（v2 再評估）
- ❌ 多語言（只支援中英文）
- ⏸️ 多用戶協作（v2 才開放，schema 已預留）

---

## 後續 Spec

| 編號 | 檔案 | 重點 |
|---|---|---|
| 01 | `01-prd.md` | user stories + functional / non-functional requirements |
| 02 | `02-system-design.md` | 系統架構、API endpoint、data model |
| 03 | `03-agent-design.md` | LLM system prompt、tool schema、structured output |
| 04 | `04-eval-plan.md` | 評估方式、測試集、metrics |
| 05 | `05-milestones.md` | 4 週里程碑切分 |
