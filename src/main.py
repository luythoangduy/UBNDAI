"""FastAPI entrypoint. Owner: Dev C (chỉ C sửa trực tiếp — TEAM_PLAN §4)."""

from fastapi import FastAPI

from src.api.v1 import router as v1_router

app = FastAPI(title="TTHC Assist", version="0.1.0")
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# TODO(C) Sprint 0: lifespan (DB init, warmup), CORS cho frontend, error handlers
# port từ C2-App-108/src/api/errors.py. Lưu ý bài học C2: nếu warmup load model
# embedding trong lifespan, phải mock được trong pytest (tránh access violation).
