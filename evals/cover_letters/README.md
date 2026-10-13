# 求職信可靠性評估案例

這裡保存人工標註案例，不是 API pytest，也不會自動呼叫 LLM。
目前 Case 2 已對應求職信 48 / v1（Matching 49、履歷 16、職缺 54），並完成目前快照的句子比對；尚不足以重跑歷史生成。

## 資料規則

- 一封信是一個 case；不同問題放進 issues，一句可以有多個標籤。
- null 代表未知；不得用目前 prompt、履歷或解析結果冒充歷史輸入。
- 原文找不到證據不等於使用者沒做過；明確否認與缺乏證據要分開。
- Matching 是分析結果，不是候選人事實來源；JD 只能支持公司需求。
- 修正句是參考寫法，不是唯一正確答案，仍需核對證據。
- first_error_stage 只有逐層比較後才能填寫，否則維持 unknown。
- evaluation_ready 必須等輸入齊備、人工審核後才可設為 true。

## 標籤

事實／證據：FABRICATION、CLAIM_INFLATION、REQUIREMENT_MIRRORING、ADJACENT_SKILL_INFERENCE、UNSUPPORTED_OUTCOME、DOMAIN_LEAP。
風格／選材：AI_TONE、POOR_RELEVANCE。
多標籤問題統計時只算一個 issue；另保留正確主張，檢查誤判。

## 下一步

1. 審核 Case 2 的實際問題句與建議修正；四筆早先摘錄保存在 unverified_excerpts，不計入此信件評分。
2. 確認本機目前快照是否能代表歷史輸入；不可僅因資料有建立時間就視為歷史版本。
3. 逐層找出問題最早出現處；無歷史快照則標記無法確認。
4. 建立人工 baseline，再分別調整 schema 或 prompt。
5. 留出部分案例作最後驗證，不拿來反覆修改規則。

## 個資與本機資料

完整未去識別化快照放在 local/（Git 忽略），不要提交聯絡資訊或完整私人履歷。
公開案例提交前仍應人工確認去識別化；目前案例只保存問題摘錄。

## 目前程式的待驗證風險

- ResumeParsed 沒有獨立 projects 與來源欄位：可能流失個人專案情境。
- 履歷抽取會截斷超過 30,000 字的內容：需確認證據是否被截掉。
- 履歷抽取要求繁中重述：需比對摘要是否改變原意。
- CoverLetterResult 描述含固定年資、專案例子與強烈語氣：需與 system prompt 一起檢查。
以上只是程式觀察，尚未證明是 Case 2 的根因。

## Case 2 本次比對

- issues 只列出已在信件 48 找到的句子；標籤仍需人工審核。
- unverified_excerpts 保留原始四筆摘要、標籤與修改建議，但不表示它們存在於信件 48。
- local_snapshot 記錄擷取時間與 SHA-256，供核對同一份檔案；hash 不能證明歷史內容或事實正確。
- snapshots 與完整信件保持 null；完整目前資料只留在忽略的 local/，此 JSON 不是可直接重播的 dataset。
- first_error_stage 維持 unknown；目前快照可觀察到求職信把 Matching 的「潛在契合」改成「具備實作經驗」，但不能據此重建歷史因果。
- 履歷解析的專案細節流失已觀察到；是否造成生成問題仍待比較實驗。

## projects 解析改動

新增 Project（name、context、implementations、technologies、source_quotes），舊資料以 projects=[] 相容。
使用者已確認尚未建立 AI coding tools 固定開發流程；這不代表歷史 prompt 已確認。
本次只做本機結構驗證，未重新呼叫 LLM、未覆蓋資料庫，也尚未證明生成品質改善。
source_quotes 的 schema 只限制結構；後續實際解析比較仍需確認引用存在原文且能支持主張。
下一步以履歷 16 的同一份抽取文字另存新解析，逐項比較兩個專案、技術歸屬與引用，不覆寫 baseline。

## 引用驗證與可讀性

解析回傳前會核對每個 source_quote：逐字符合直接保留；只有空白不同時，依字元位置還原成原文片段。
大小寫、標點或實際文字不同不接受；空引用也不接受。任何一段失敗時整次解析回傳 None，沿用既有失敗處理，不自動補造證據。
比對來源是實際送給模型的文字（若截斷則是截斷後），不是完整未送出的文字。
這只證明引用存在；不驗證專案歸屬或主張是否被支持。忽略空白可能消除詞界，因此仍須語意審核。
一般欄位可讀性與跨段落技術歸屬由解析指令要求，尚需下一次實際生成驗證，不能用本機引用驗證代替。

## 2026-10-12 實際解析驗證

使用履歷 16 保存的相同原文，單次 Gemini 解析，未覆寫資料庫。
本機結果：local/resume_16_validated_20261012T085753Z.json（私人資料，不提交）。

- 兩個個人專案保留，名稱與實作敘述的多餘字元空白已改善。
- 程式驗證／還原後 7 段引用皆為原文片段；不代表模型原始輸出全部逐字吻合。
- ig-clone technologies 仍缺少原文摘要明確提到的 Node.js、MongoDB，跨段落完整性未通過。
- 此次只驗證解析，不代表求職信幻覺減少或所有履歷都能正確處理。
- 結果可作階段性紀錄，尚未完成全部驗收，不自動追加付費重試。

## 自己執行比較

兩個檔案是不同次解析：projects 為較早的模型解析結果，validated 為後一次解析且經程式引用驗證／還原的結果。
外層 metadata 版本不同；parsed_data 才是解析內容。比較前腳本檢查履歷 ID 與原文 hash。

在專案根目錄執行：

```bash
.venv/bin/python scripts/compare_resume_projects.py \
  --source evals/cover_letters/local/case_002_current_db.json \
  --before evals/cover_letters/local/resume_16_projects_20261011T183706Z.json \
  --after evals/cover_letters/local/resume_16_validated_20261012T085753Z.json \
  --expectations evals/cover_letters/resume_16_expectations.json \
  --output evals/cover_letters/local/resume_16_comparison.json
```

不呼叫 API、不更新 DB。輸出成功只代表完成比較，不代表所有檢查通過；請查看遺漏項與引用統計。
expectations 是人工選定的最小檢查範圍，未列入的技術不代表不重要。
這屬於資料解析與評估，不是 Agent 工具呼叫迴圈。

## 預期清單 v2：評分也要有證據

每項 technology 附 evidence_location 與 evidence_quote，且綁定 resume_id。
脚本在比較前確認非空引文存在於原文（只忽略空白，不忽略大小寫及標點），並確認引文包含專案名與技術名；不符即停止，不產生新報告。
位置名稱為人工標記，程式不驗證段落標題；共同出現在引文也不保證語意上的歸屬，仍需人工審核。
本次 Node.js、MongoDB 的依據是個人簡介明確寫 ig-clone 的技術組合，不是全域 skills。
命令不變，終端與 JSON 報告都顯示預期證據。此版會拒絕舊版只有技術名稱的清單。
