from fastapi import APIRouter

from app.api.v1 import admin, auth, chat, documents, edits, folders, reviews, search, signatures, translations

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(folders.router)
api_router.include_router(reviews.router)
api_router.include_router(edits.router)
api_router.include_router(signatures.router)
api_router.include_router(chat.router)
api_router.include_router(translations.router)
api_router.include_router(search.router)
api_router.include_router(admin.router)
