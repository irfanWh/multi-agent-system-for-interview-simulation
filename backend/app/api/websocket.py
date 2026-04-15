import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_db
from app.models.orm import Session
from app.agents.interviewer import run_interview_graph
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/session/{session_id}")
async def interview_websocket(
    websocket: WebSocket, 
    session_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for the real-time interview.
    Accepts the connection, loads the session plan, and starts Agent 3 (Interviewer).
    Protocol:
    - Server -> Client: {"type": "question" | "follow_up" | "session_complete" | "error", "text": "..."}
    - Client -> Server: {"type": "answer", "text": "..."}
    """
    await websocket.accept()
    
    # 1. Fetch Session
    session_obj = await db.scalar(select(Session).where(Session.id == session_id))
    if not session_obj:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return
        
    session_plan = session_obj.session_plan
    if not session_plan:
        await websocket.send_json({"type": "error", "message": "No session plan available. Ensure Orchestrator ran."})
        await websocket.close()
        return
        
    # 2. I/O Callbacks for the Graph
    async def send_msg(msg: dict):
        await websocket.send_json(msg)
        
    async def recv_msg() -> dict:
        try:
            data = await websocket.receive_json()
            return data
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
            return {"type": "disconnect"}
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            return {"type": "answer", "text": ""}

    # 3. Invoke Interviewer Graph Loop
    try:
        await run_interview_graph(
            session_id=str(session_obj.id),
            session_plan=session_plan,
            send_fn=send_msg,
            recv_fn=recv_msg,
            db=db
        )
    except Exception as e:
        logger.error(f"Interview graph error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error during interview."})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
