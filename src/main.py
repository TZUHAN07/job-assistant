from fastapi import FastAPI

app = FastAPI(
    title="job-assistant",
    description="AI 求職助手 — 履歷分析、JD 匹配評分、cover letter 生成",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint for uptime monitoring."""
    return {"status": "ok", "service": "job-assistant"}


@app.get("/")
async def root():
    return {
        "message": "job-assistant API",
        "docs": "/docs",
        "health": "/health",
    }