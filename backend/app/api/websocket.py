import uuid
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_db
from app.models.orm import Session
from app.agents.interviewer import run_interview_graph
from app.services.stt_service import WhisperService
from app.services.audio_buffer import AudioBuffer

import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/session/{session_id}")
async def interview_websocket(
    websocket: WebSocket, 
    session_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db)
):
    await websocket.accept()
    
    session_obj = await db.scalar(select(Session).where(Session.id == session_id))
    if not session_obj:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return
        
    session_plan = session_obj.session_plan
    if not session_plan:
        await websocket.send_json({"type": "error", "message": "No session plan available."})
        await websocket.close()
        return

    # Services
    whisper_service = WhisperService()
    audio_buffer = AudioBuffer()
    
    # State tracking
    interaction_mode = "text"
    pending_answer = None

    async def send_msg(msg: dict):
        await websocket.send_json(msg)

    async def process_binary(data: bytes):
        """Process incoming audio, accumulate, and transcribe on silence."""
        nonlocal pending_answer
        
        is_silence = whisper_service.detect_silence(data)
        audio_buffer.add_chunk(data, is_silence)
        
        utterance = audio_buffer.get_complete_utterance()
        if utterance:
            # Silence detected > 500ms, transcribe
            audio_buffer.reset()
            transcript = await whisper_service.transcribe(utterance)
            if transcript.strip():
                # Yield answer to the graph
                pending_answer = transcript.strip()
                # Send confirmation back to client so they see their live text
                await send_msg({"type": "transcript", "text": pending_answer})

    async def recv_msg() -> Dict[str, Any]:
        """
        Receives messages from WebSocket.
        If mode='audio', absorbs binary frames until an utterance is complete,
        then returns {"type": "answer", "text": transcript}.
        If mode='text', returns immediately.
        """
        nonlocal interaction_mode, pending_answer
        
        while True:
            # If we already got an audio answer buffered, flush it and return
            if pending_answer is not None:
                ans = pending_answer
                pending_answer = None
                return {"type": "answer", "text": ans}

            try:
                # Wait for next frame
                message = await websocket.receive()
                
                if "bytes" in message:
                    if interaction_mode == "audio":
                        # Process audio chunk
                        await process_binary(message["bytes"])
                    else:
                        logger.warning("Received binary but mode is text")
                        
                elif "text" in message:
                    import json
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "set_mode":
                            interaction_mode = data.get("mode", "text")
                            logger.info(f"Interaction mode set to: {interaction_mode}")
                        elif data.get("type") == "answer":
                            if interaction_mode == "text":
                                return {"type": "answer", "text": data.get("text", "")}
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON received")
                        
                elif message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect()

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected")
                return {"type": "disconnect"}
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                await asyncio.sleep(1) # Prevent tight CPU loop on parse fail

    # Graph loop
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
    finally:
        try:
            await websocket.close()
        except:
            pass
