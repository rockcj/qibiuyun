"""Scene configuration router – GET /api/scenes."""

from fastapi import APIRouter

from services.scene_service import get_all_scenes, get_scene_list

router = APIRouter(prefix="/api", tags=["scenes"])


@router.get("/scenes")
async def list_scenes(full: bool = False):
    """
    Return scene configuration.

    - `full=false` (default): lightweight list for homepage cards.
    - `full=true`: complete configuration including topics, roles, and rubrics.
    """
    if full:
        return {"scenes": get_all_scenes()}
    return {"scenes": get_scene_list()}
