"""固定措辭偏好，不用詞彙命中推論候選人經歷真假。"""
from src.schemas.cover_letter_review import ReviewIssue

WORDING_RULES = {
    "旨在": "直接寫「我希望應徵……」，保留原職缺資訊。",
    "我深信": "刪除自我保證的語氣，改述履歷已支持的具體實作。",
    "深感興趣": "直接說明吸引自己的工作內容，不新增公司資訊。",
    "高度契合": "改述經驗與職缺的具體連結，不宣稱完全符合。",
    "帶來即戰力": "改述已完成的專案實作，不保證入職後的勝任程度。",
}
FIELDS = ("title", "opening", "why_me", "why_company", "call_to_action", "full_content")


def check_wording(letter):
    issues = []
    for phrase, suggestion in WORDING_RULES.items():
        # 同一句常同時出現在段落與全文；每條規則只提示一次，避免重複列滿畫面。
        field = next((key for key in FIELDS if phrase in getattr(letter, key)), None)
        if field is not None:
            issues.append(ReviewIssue(
                field=field, quote=phrase, category="ai_tone", evidence_ids=[],
                reason=f"命中固定措辭偏好「{phrase}」；這是文字風格提醒，不代表經歷不實。",
                suggested_revision=suggestion,
            ))
    return issues


def merge_wording_review(review, letter):
    issues = list(review.issues)
    existing = {(issue.category, issue.quote) for issue in issues}
    issues.extend(issue for issue in check_wording(letter)
                  if (issue.category, issue.quote) not in existing)
    # 規則可成功、模型卻失敗；不可把部分檢查誤標為完整成功。
    status = review.status if review.status == "review_failed" else (
        "needs_revision" if issues else "no_issues_found"
    )
    return review.model_copy(update={"status": status, "issues": issues})
