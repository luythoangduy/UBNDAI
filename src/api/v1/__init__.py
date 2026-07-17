from fastapi import APIRouter

from src.api.v1 import cases, chat, documents, ops

router = APIRouter(prefix="/api/v1")
router.include_router(chat.router)
router.include_router(cases.router)
router.include_router(documents.router)
router.include_router(ops.router)
# TODO(C): include auth router sau khi port từ C2-App-108
