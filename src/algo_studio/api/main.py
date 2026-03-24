# src/algo_studio/api/main.py
from fastapi import FastAPI
from algo_studio.api.routes import tasks, hosts

app = FastAPI(
    title="AlgoStudio API",
    description="AI Algorithm Platform API",
    version="0.1.0"
)

app.include_router(tasks.router)
app.include_router(hosts.router)

@app.get("/health")
async def health():
    return {"status": "ok"}