from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return success_response("OK", {"status": "healthy"})
