# src/algo_studio/api/main.py
from fastapi import FastAPI
from algo_studio.api.routes import tasks, hosts, cluster

app = FastAPI(
    title="AlgoStudio API",
    description="AI Algorithm Platform API",
    version="0.2.0"
)

app.include_router(tasks.router)
app.include_router(hosts.router)
app.include_router(cluster.router)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {
        "name": "AlgoStudio API",
        "version": "0.2.0",
        "endpoints": {
            "tasks": "/api/tasks",
            "hosts": "/api/hosts",
            "cluster": "/api/cluster"
        }
    }