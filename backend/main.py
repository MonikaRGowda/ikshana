from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from routers import auth
from routers import booth
from routers import election   
from routers import audit     
from routers import biometric   
from realtime import sio
# Create FastAPI app
app = FastAPI(title="Ikshana — Electoral Authentication System")

# Allow React frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(audit.router, prefix="/api", tags=["Audit Logs"])    
app.include_router(biometric.router, prefix="/api", tags=["Biometric"]) 
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
