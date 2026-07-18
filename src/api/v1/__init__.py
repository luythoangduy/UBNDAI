from fastapi import APIRouter

from src.api.v1 import (
    cases,
    application_management,
    chat,
    citizen,
    documents,
    drafts,
    officer,
    ops,
    procedures,
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
router.include_router(application_management.router)
router.include_router(citizen.router)
router.include_router(procedures.router)
# TODO(C): include auth router sau khi port từ C2-App-108
