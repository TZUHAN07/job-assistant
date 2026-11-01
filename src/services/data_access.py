"""資料查詢共用的擁有者條件；套用在 SQL 階段，避免先載入別人的資料。"""

from sqlalchemy import and_, or_

from src.models import Application, CoverLetter, Job, Matching, Resume


def matching_owned_by(user_id: int):
    # Matching 自己與來源都必須屬於本人，舊資料若關聯錯誤也不能漏出。
    return and_(
        Matching.user_id == user_id,
        Matching.resume.has(Resume.user_id == user_id),
        Matching.job.has(Job.user_id == user_id),
    )


def letter_owned_by(user_id: int):
    return and_(
        CoverLetter.user_id == user_id,
        CoverLetter.matching.has(matching_owned_by(user_id)),
    )


def application_owned_by(user_id: int):
    return and_(
        Application.user_id == user_id,
        Application.resume.has(Resume.user_id == user_id),
        Application.job.has(Job.user_id == user_id),
        Application.matching.has(and_(
            matching_owned_by(user_id),
            Matching.resume_id == Application.resume_id,
            Matching.job_id == Application.job_id,
        )),
        or_(
            Application.cover_letter_id.is_(None),
            Application.cover_letter.has(and_(
                CoverLetter.user_id == user_id,
                CoverLetter.matching_id == Application.matching_id,
            )),
        ),
    )
