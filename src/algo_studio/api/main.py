# src/algo_studio/api/main.py
from fastapi import FastAPI
from algo_studio.api.routes import tasks, hosts, cluster, deploy, audit
from algo_studio.api.middleware.rbac import RBACMiddleware
from algo_studio.api.middleware.audit import AuditMiddleware

app = FastAPI(
    title="AlgoStudio API",
    description="AI Algorithm Platform API",
    version="0.2.0"
)

# Add RBAC middleware for permission checking
app.add_middleware(RBACMiddleware)

# Add Audit middleware for logging all API operations
# Note: Audit middleware should come after RBAC to capture authenticated user info
app.add_middleware(AuditMiddleware)

app.include_router(tasks.router)
app.include_router(hosts.router)
app.include_router(cluster.router)
app.include_router(deploy.router)
app.include_router(audit.router)

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
            "cluster": "/api/cluster",
            "deploy": "/api/deploy",
            "audit": "/api/audit/logs"
        }
    }