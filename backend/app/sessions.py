"""
Session Manager for tracking active monitoring sessions and thread execution.
Enforces single-active-session limit, bounded queues, and proper teardown.
"""
import asyncio
import time
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.inference.tracking_core import SessionInferencePipeline

class ActiveSession:
    def __init__(self, session_id: str, camera_label: str = "Camera 01"):
        self.session_id = session_id
        self.camera_label = camera_label
        self.created_at = time.time()
        self.created_at_ms = int(self.created_at * 1000)
        self.pipeline = SessionInferencePipeline(session_id)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"inf-{session_id}")
        self.is_active = True
        self.last_activity_time = time.time()

    def close(self):
        self.is_active = False
        self.pipeline.close()
        self.executor.shutdown(wait=False)

class SessionManager:
    """Singleton session manager."""
    def __init__(self):
        self._sessions: Dict[str, ActiveSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, camera_label: str = "Webcam 01") -> ActiveSession:
        async with self._lock:
            # Check single active session limit
            if len(self._sessions) >= settings.MAX_CONCURRENT_SESSIONS:
                # Remove inactive/stale sessions older than 30 minutes if any
                now = time.time()
                stale_ids = [sid for sid, s in self._sessions.items() if now - s.last_activity_time > 1800]
                for sid in stale_ids:
                    self._sessions.pop(sid).close()

                if len(self._sessions) >= settings.MAX_CONCURRENT_SESSIONS:
                    raise ValueError("Hệ thống đang phục vụ một phiên thi khác. Vui lòng dừng phiên trước đó.")

            session = ActiveSession(session_id, camera_label)
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[ActiveSession]:
        return self._sessions.get(session_id)

    def get_active_session(self) -> Optional[ActiveSession]:
        """Return the single active session used by the MVP deployment."""
        return next(iter(self._sessions.values()), None)

    async def close_session(self, session_id: str) -> Optional[ActiveSession]:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.close()
            return session

    def active_session_count(self) -> int:
        return len(self._sessions)

session_manager = SessionManager()
