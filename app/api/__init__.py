# API routes
from fastapi import APIRouter
from app.api.patients import router as patients_router
from app.api.questionnaire import router as questionnaire_router
from app.api.status import router as status_router
from app.api.checklist import router as checklist_router
from app.api.finance import router as finance_router
from app.api.referral import router as referral_router
from app.api.ai import router as ai_assistant_router
from app.api.export import router as export_router

# Combine all routers
router = APIRouter()
router.include_router(patients_router)
router.include_router(questionnaire_router)
router.include_router(status_router)
router.include_router(checklist_router)
router.include_router(finance_router)
router.include_router(referral_router)
router.include_router(ai_assistant_router)
router.include_router(export_router)

__all__ = ["router"]

