from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.auth.router import router as auth_router
from app.rooms.router import router as rooms_router
from app.cards.router import router as cards_router
from app.ws.router import router as ws_router

app = FastAPI(title="SyncBoard", version="0.1.0")

# Register routers
app.include_router(auth_router)
app.include_router(rooms_router)
app.include_router(cards_router)
app.include_router(ws_router)

# Allow the SvelteKit frontend to make cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    """Simple endpoint to verify the API is running."""
    return {"status": "ok"}