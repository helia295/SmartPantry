from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    """Health check for load balancers and monitoring."""
    return {"status": "ok", "service": "smartpantry-api"}
