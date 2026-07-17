from fastapi import APIRouter

from src.api.v1 import (
    cases,
    chat,
    citizen,
    documents,
    drafts,
    officer,
    ops,
    validation,
)

router = APIRouter(prefix="/api/v1")
router.include_router(chat.router)
router.include_router(cases.router)
router.include_router(documents.router)
router.include_router(drafts.router)
router.include_router(validation.router)
router.include_router(ops.router)
router.include_router(officer.router)
router.include_router(citizen.router)
# TODO(C): include auth router sau khi port từ C2-App-108
