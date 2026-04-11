"""CRUD /personas — agent persona management."""

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth_middleware import CurrentUser
from app.models.persona import PersonaCreate, PersonaResponse, PersonaUpdate
from app.services.persona_service import PersonaService, get_persona_service
from app.services.subscription_service import get_subscription_service

router = APIRouter()


@router.get("")
async def list_personas(
    user: CurrentUser,
    svc: PersonaService = Depends(get_persona_service),  # noqa: B008
) -> list[PersonaResponse]:
    """Return defaults + user-created personas."""
    return await svc.list_personas(user.uid)


@router.get("/{persona_id}")
async def get_persona(
    persona_id: str,
    user: CurrentUser,
    svc: PersonaService = Depends(get_persona_service),  # noqa: B008
) -> PersonaResponse:
    """Get a single persona by ID."""
    return await svc.get_persona(user.uid, persona_id)


@router.post("", status_code=201)
async def create_persona(
    body: PersonaCreate,
    user: CurrentUser,
    svc: PersonaService = Depends(get_persona_service),  # noqa: B008
) -> PersonaResponse:
    """Create a custom persona."""
    sub_svc = get_subscription_service()
    flags = sub_svc.get_feature_flags(user.uid)
    if not flags.get("custom_personas", False):
        raise HTTPException(status_code=403, detail="Custom personas require a Pro or higher plan.")
    all_personas = await svc.list_personas(user.uid)
    custom_count = sum(1 for p in all_personas if getattr(p, "is_custom", False))
    if not sub_svc.check_feature(user.uid, "max_personas", custom_count):
        raise HTTPException(status_code=403, detail="Persona limit reached for your plan.")
    return await svc.create_persona(user.uid, body)


@router.put("/{persona_id}")
async def update_persona(
    persona_id: str,
    body: PersonaUpdate,
    user: CurrentUser,
    svc: PersonaService = Depends(get_persona_service),  # noqa: B008
) -> PersonaResponse:
    """Update a user-created persona (defaults are immutable)."""
    return await svc.update_persona(user.uid, persona_id, body)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: str,
    user: CurrentUser,
    svc: PersonaService = Depends(get_persona_service),  # noqa: B008
) -> None:
    """Delete a user-created persona (defaults cannot be deleted)."""
    await svc.delete_persona(user.uid, persona_id)
