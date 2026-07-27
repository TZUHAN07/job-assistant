from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db

from src.routers import resume as resume_router
from src.routers import jobs as jobs_router
from src.routers import matchings as matchings_router
from src.routers import cover_letters as cover_letters_router

app = FastAPI(
    title="job-assistant",
    description="AI 求職助手 — 履歷分析、JD 匹配評分、cover letter 生成",
    version="0.1.0",
)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint for uptime monitoring."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {
        "status": "ok",
        "service": "job-assistant",
        "db_status": db_status,
    }


@app.get("/")
async def root():
    return {
        "message": "job-assistant API",
        "docs": "/docs",
        "health": "/health",
    }


app.include_router(resume_router.router)
app.include_router(jobs_router.router)
app.include_router(matchings_router.router)
app.include_router(cover_letters_router.router)