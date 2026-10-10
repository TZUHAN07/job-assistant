# 求職信可靠性評估案例

這裡保存人工標註案例，不是 API pytest，也不會自動呼叫 LLM。
目前 Case 2 是使用者提供的句子摘錄，尚不足以重跑歷史生成。

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

1. 確認 Case 2 原始信件；matching 49 目前只確認職稱吻合。
2. 保存當時 PDF 抽取文字、履歷解析、JD、Matching 與信件。
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
