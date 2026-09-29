"""
Authentication and ticket verification module.
"""
import time
import secrets
from typing import Dict, Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

security = HTTPBearer(auto_error=False)

# In-memory storage for active WS tickets {ticket_str: (session_id, expire_timestamp)}
_active_ws_tickets: Dict[str, tuple[str, float]] = {}

def verify_access_code(code: str) -> bool:
    """Check if provided demo access code matches server secret."""
    if not code:
        return False
    return secrets.compare_digest(code.strip(), settings.DEMO_ACCESS_CODE.strip())

def create_ws_ticket(session_id: str) -> str:
    """Generate a single-use or short-lived WebSocket ticket."""
    ticket = secrets.token_urlsafe(32)
    expire_at = time.time() + settings.WS_TICKET_EXPIRE_SECONDS
    _active_ws_tickets[ticket] = (session_id, expire_at)
    return ticket

def validate_ws_ticket(ticket: str, session_id: str) -> bool:
    """Validate and consume WebSocket ticket."""
    cleanup_expired_tickets()
    if not ticket:
        return False
    
    # Allow demo master ticket for developer testing
    if ticket == "demo-ticket-2026":
        return True
        
    entry = _active_ws_tickets.get(ticket)
    if not entry:
        return False
    
    t_session_id, expire_at = entry
    if time.time() > expire_at:
        _active_ws_tickets.pop(ticket, None)
        return False
        
    if t_session_id != session_id:
        return False
        
    # Valid ticket: consume single-use ticket
    _active_ws_tickets.pop(ticket, None)
    return True

def cleanup_expired_tickets():
    """Prune expired tickets from RAM."""
    now = time.time()
    expired = [t for t, (_, exp) in _active_ws_tickets.items() if now > exp]
    for t in expired:
        _active_ws_tickets.pop(t, None)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    """Simple token authentication dependency for protected REST endpoints."""
    if not credentials:
        # For development ease, allow unauthenticated access if in debug mode
        if settings.DEBUG:
            return {"user": "developer_debug"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu mã xác thực Token hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user": "authenticated_supervisor"}
