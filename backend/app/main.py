from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.resumes import router as resumes_router
from app.api.sessions import router as sessions_router
from app.api.exchanges import router as exchanges_router
from app.api.websocket import router as websocket_router

from app.services.qdrant_service import QdrantService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # App startup — initialise Qdrant collections
    qdrant = QdrantService.get_instance()
    await qdrant.init_collections()
    yield
    # App shutdown
    pass

app = FastAPI(
    title="InterviewAI API",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(resumes_router, tags=["resumes"])
app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
app.include_router(exchanges_router, tags=["exchanges"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0"
    }
