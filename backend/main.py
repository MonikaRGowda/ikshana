from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from routers import auth
from routers import booth
from routers import election   
from routers import biometric   
from routers import admin_auth
from routers import admin_ro
from routers import admin_ceo
from routers import evidence
from realtime import sio
from schema import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


# Create FastAPI app
app = FastAPI(title="Ikshana — Electoral Authentication System", lifespan=lifespan)

# Allow React frontend to talk to backend.
# NOTE: allow_origins=["*"] + allow_credentials=True is invalid per the
# CORS spec — browsers refuse to send/store cookies on a wildcard-origin
# response. Since RO/CEO sessions now depend on a cookie, this must be a
# specific origin. Set FRONTEND_ORIGIN in .env to match wherever your
# frontend dev server actually runs (Vite default is 5173).
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Combine FastAPI + Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# ─── ROUTES ───────────────────────────────────────────────────

app.include_router(auth.router, prefix="/api", tags=["Authentication"]) 
app.include_router(booth.router, prefix="/api", tags=["Booth Officers"])
app.include_router(election.router, prefix="/api", tags=["Elections"])  
app.include_router(biometric.router, prefix="/api", tags=["Biometric"]) 
app.include_router(admin_auth.router, tags=["Admin Auth"])
app.include_router(admin_ro.router, tags=["Admin RO"])
app.include_router(admin_ceo.router, tags=["Admin CEO"])
app.include_router(evidence.router, tags=["Evidence"])
@app.get("/")
async def root():
    return {"message": "Ikshana Electoral Authentication System is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

# ─── SOCKET.IO EVENTS ─────────────────────────────────────────

# ─── RUN ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:socket_app", host="0.0.0.0", port=8000, reload=True)