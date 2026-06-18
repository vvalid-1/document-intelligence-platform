from fastapi import APIRouter

from app.api.v1 import admin, auth, chat, documents, edits, reviews, signatures

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(reviews.router)
api_router.include_router(edits.router)
api_router.include_router(signatures.router)
api_router.include_router(chat.router)
api_router.include_router(admin.router)
