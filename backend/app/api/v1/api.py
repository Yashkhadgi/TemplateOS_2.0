from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, system, templates

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
