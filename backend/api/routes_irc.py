from fastapi import APIRouter

from hosnt12.irc import adapters
from hosnt12.schemas import IRCCheck, IRCOption, IRCPlacement, IRCPreview

router = APIRouter(prefix="/api/irc")


@router.get("/options")
def options() -> list[IRCOption]:
    return adapters.options()


@router.post("/preview-loads")
def preview(body: IRCPlacement) -> IRCPreview:
    return adapters.preview_loads(body)


@router.post("/check")
def check(body: IRCPlacement) -> list[IRCCheck]:
    return adapters.check(body)
