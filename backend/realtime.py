"""Socket.IO transport and booth-session authentication."""
import socketio

from database import get_election_db


sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
BOOTH_ROOM = "active-booths"


def _valid_booth_session(session_token: str, booth_id: str) -> bool:
    if not session_token or not booth_id:
        return False

    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM booth_sessions
            WHERE session_token = %s AND booth_id = %s AND is_active = TRUE
            """,
            (session_token, booth_id),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


@sio.event
async def connect(sid, environ, auth):
    """Accept sockets only when they present an active booth session."""
    auth = auth or {}
    booth_id = str(auth.get("booth_id", "")).upper()
    session_token = str(auth.get("session_token", ""))

    try:
        is_valid = _valid_booth_session(session_token, booth_id)
    except Exception as error:
        print(f"Socket authentication error: {error}")
        is_valid = False

    if not is_valid:
        raise ConnectionRefusedError("Invalid or expired booth session")

    await sio.save_session(sid, {"booth_id": booth_id})
    await sio.enter_room(sid, BOOTH_ROOM)
    await sio.enter_room(sid, f"booth:{booth_id}")
    print(f"Booth connected: {booth_id} ({sid})")


@sio.event
async def disconnect(sid):
    try:
        session = await sio.get_session(sid)
    except KeyError:
        session = {}
    booth_id = session.get("booth_id", "unknown") if session else "unknown"
    print(f"Booth disconnected: {booth_id} ({sid})")


async def broadcast_booth_event(event: str, payload: dict) -> None:
    """Send a committed authentication/fraud event to every active booth."""
    await sio.emit(event, payload, room=BOOTH_ROOM)
