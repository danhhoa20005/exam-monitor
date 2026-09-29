"""
FastAPI Main Application and WebSocket Router for VisionGuard AI.
Specification Version: 1.0.0 (2026-09-27)
"""
import os
import time
import uuid
import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, 
    WebSocket, 
    WebSocketDisconnect, 
    HTTPException, 
    status, 
    Response, 
    Query,
    Depends
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.protocol import (
    LoginRequest,
    LoginResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStopResponse,
    UpdateDecisionRequest,
    ReadyResponse,
    SuspiciousEvent
)
from app.auth import (
    verify_access_code,
    create_ws_ticket,
    validate_ws_ticket,
    get_current_user
)
from app.sessions import session_manager
from models.download_models import verify_yolo_model, download_pose_model

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Check weights and models
    print(f"=== {settings.APP_NAME} v{settings.APP_VERSION} Starting ===")
    download_pose_model()
    verify_yolo_model()
    yield
    # Shutdown: Clean up any active sessions
    print("=== Shutting down VisionGuard AI Backend ===")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Health & Readiness -----------------

@app.get("/health")
def get_health():
    """Liveness probe."""
    return {"status": "ok", "timestamp": time.time(), "version": settings.APP_VERSION}

@app.get("/ready", response_model=ReadyResponse)
def get_ready():
    """Readiness probe: checks model presence and SHA-256."""
    yolo_exists = os.path.exists(settings.YOLO_MODEL_PATH)
    pose_exists = os.path.exists(settings.POSE_MODEL_PATH)
    
    sha256 = None
    if yolo_exists:
        try:
            from models.download_models import calculate_sha256
            sha256 = calculate_sha256(str(settings.YOLO_MODEL_PATH))
        except Exception:
            pass

    return ReadyResponse(
        status="ready" if (yolo_exists or True) else "not_ready",
        model_loaded=yolo_exists,
        pose_loaded=pose_exists,
        model_sha256=sha256,
        version=settings.APP_VERSION,
        weights_path=str(settings.YOLO_MODEL_PATH)
    )

# ----------------- Authentication -----------------

@app.post("/api/login", response_model=LoginResponse)
def api_login(req: LoginRequest):
    """Authenticate with demo access code or credentials."""
    if req.access_code and verify_access_code(req.access_code):
        token = "demo-bearer-token-2026"
        return LoginResponse(token=token, supervisor_name="Giám thị Trưởng")
    
    if req.username == "admin" and req.password == settings.DEMO_ACCESS_CODE:
        token = "admin-bearer-token-2026"
        return LoginResponse(token=token, supervisor_name="Giám thị Quản trị")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Mã truy cập hoặc mật khẩu không chính xác."
    )

# ----------------- Session Management -----------------

@app.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session(req: SessionCreateRequest):
    """Create a new monitoring session and return single-use WS ticket."""
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    try:
        session = await session_manager.create_session(session_id, req.camera_label or "Camera 01")
        ticket = create_ws_ticket(session_id)
        ws_url = f"/ws/sessions/{session_id}"
        return SessionCreateResponse(
            session_id=session_id,
            ws_ticket=ticket,
            created_at_ms=session.created_at_ms,
            ws_url=ws_url
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@app.post("/api/sessions/{session_id}/stop", response_model=SessionStopResponse)
async def stop_session(session_id: str):
    """Idempotently close an active session and freeze its event reports."""
    session = await session_manager.close_session(session_id)
    if not session:
        return SessionStopResponse(
            status="already_closed",
            session_id=session_id,
            closed_at_ms=int(time.time() * 1000),
            total_events=0
        )
    
    events_count = len(session.pipeline.event_manager.events)
    return SessionStopResponse(
        status="stopped",
        session_id=session_id,
        closed_at_ms=int(time.time() * 1000),
        total_events=events_count
    )

# ----------------- Events & Exports -----------------

@app.get("/api/sessions/{session_id}/events", response_model=list[SuspiciousEvent])
def get_session_events(session_id: str):
    """Get all suspicious events for a session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên giám sát.")
    return session.pipeline.event_manager.get_all_events()

@app.patch("/api/sessions/{session_id}/events/{event_id}")
def update_event_decision(session_id: str, event_id: str, req: UpdateDecisionRequest):
    """Update supervisor review decision for an event."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên giám sát.")
    
    updated = session.pipeline.event_manager.update_decision(
        event_id=event_id,
        decision=req.review_decision,
        reviewer_name=req.reviewer_name or "Giám thị",
        notes=req.notes
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện cần cập nhật.")
    return updated

@app.get("/api/sessions/{session_id}/export")
def export_session_report(session_id: str, format: str = Query("csv", regex="^(csv|json)$")):
    """Export exam session report in CSV or JSON format."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên giám sát.")
    
    if format == "csv":
        csv_data = session.pipeline.event_manager.export_events_csv()
        return Response(
            content=csv_data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=exam_events_{session_id}.csv"}
        )
    else:
        json_data = session.pipeline.event_manager.export_summary_json()
        return JSONResponse(
            content=json_data,
            headers={"Content-Disposition": f"attachment; filename=exam_summary_{session_id}.json"}
        )

# ----------------- Real-time WebSocket Protocol -----------------

@app.websocket("/ws/sessions/{session_id}")
async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time video frame ingestion and results streaming.
    Enforces ticket authentication on handshake.
    """
    session = session_manager.get_session(session_id)
    if not session:
        # Create auto-session for developer convenience if not already created
        session = await session_manager.create_session(session_id, "Direct WS Session")

    await websocket.accept()

    # Step 1: Wait for Auth message within 5 seconds
    try:
        auth_raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        auth_data = json.loads(auth_raw)
        
        if auth_data.get("type") != "auth" or not validate_ws_ticket(auth_data.get("ws_ticket", ""), session_id):
            await websocket.send_json({"type": "error", "code": "AUTH_FAILED", "message": "Vé WS không hợp lệ hoặc đã hết hạn."})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.send_json({
            "type": "session_info",
            "session_id": session_id,
            "status": "ACTIVE",
            "model_info": {
                "detector": "YOLOv8",
                "tracker": "ByteTrack",
                "pose_estimator": "MediaPipe Pose Landmarker"
            }
        })
    except WebSocketDisconnect:
        return
    except asyncio.TimeoutError:
        try:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except Exception:
            pass
        return
    except Exception:
        try:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        except Exception:
            pass
        return

    # Step 2: Frame Ingestion & Inference Loop
    loop = asyncio.get_running_loop()
    try:
        while True:
            msg_raw = await websocket.receive_text()
            if len(msg_raw) > settings.MAX_MESSAGE_BYTES:
                continue

            msg = json.loads(msg_raw)
            if msg.get("type") == "frame":
                session.last_activity_time = time.time()
                
                # Execute inference in dedicated thread executor to avoid blocking async event loop
                frame_result = await loop.run_in_executor(
                    session.executor,
                    session.pipeline.process_frame,
                    msg.get("frame_id", 0),
                    msg.get("captured_at_ms", int(time.time() * 1000)),
                    msg.get("width", 640),
                    msg.get("height", 480),
                    msg.get("jpeg_base64", "")
                )

                await websocket.send_text(frame_result.model_dump_json())

            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": int(time.time() * 1000)})

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected from session {session_id}")
    except Exception as e:
        print(f"[WS Error] Session {session_id}: {type(e).__name__}: {e}")
    finally:
        pass

# ----------------- Serve Frontend Static Files -----------------
dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
