"""FastAPI API routers — replaces Flask Blueprints."""
from __future__ import annotations

from chatbot_viva.api.routers.health import router as health_router
from chatbot_viva.api.routers.chat import router as chat_router
from chatbot_viva.api.routers.conversations import router as conversations_router
from chatbot_viva.api.routers.legal import router as legal_router
from chatbot_viva.api.routers.auth import router as auth_router
from chatbot_viva.api.routers.admin import router as admin_router

ALL_ROUTERS = [
    health_router,
    chat_router,
    conversations_router,
    legal_router,
    auth_router,
    admin_router,
]
