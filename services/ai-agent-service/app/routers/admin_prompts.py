from fastapi import APIRouter
from app.core import prompt_loader

router = APIRouter(prefix="/admin/prompts", tags=["admin-prompts"])


@router.post("/reload")
async def reload_prompts():
    count = prompt_loader.reload_cache()
    return {"success": True, "reloaded": count}
