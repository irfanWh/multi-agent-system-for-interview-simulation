import uuid
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from enum import Enum
import asyncio

from app.api.deps import get_db
from app.models.orm import Session, RecruiterInterview, SessionStatus, get_utc_now
from app.agents.interviewer import run_interview_graph
from app.services.stt_service import WhisperService
from app.services.audio_buffer import AudioBuffer
from app.services.tts_service import TTSService
from app.services.recruiter_interview_service import hash_access_code, utc_now

logger = logging.getLogger(__name__)
router = APIRouter()

class SessionState(Enum):
    WAITING_FOR_SPEECH = "waiting"
    PROCESSING_STT = "stt"
    AGENT_THINKING = "thinking"
    PLAYING_TTS = "tts"

@router.websocket("/session/{session_id}")
async def interview_websocket(
    websocket: WebSocket, 
    session_id: uuid.UUID, 
    access_code: str | None = None,
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

    recruiter_interview = await db.scalar(
        select(RecruiterInterview).where(RecruiterInterview.session_id == session_id)
    )
    if recruiter_interview:
        if not access_code or recruiter_interview.code_hash != hash_access_code(access_code):
            await websocket.send_json({"type": "error", "message": "Invalid interview access code"})
            await websocket.close()
            return
        if recruiter_interview.deadline_at < utc_now():
            recruiter_interview.status = SessionStatus.expired
            session_obj.status = SessionStatus.expired
            await db.commit()
            await websocket.send_json({"type": "error", "message": "Interview code has expired"})
            await websocket.close()
            return
        if recruiter_interview.status in {SessionStatus.completed, SessionStatus.expired, SessionStatus.cancelled}:
            await websocket.send_json({"type": "error", "message": f"Interview is {recruiter_interview.status.value}"})
            await websocket.close()
            return

        recruiter_interview.status = SessionStatus.in_progress
        session_obj.status = SessionStatus.in_progress
        session_obj.started_at = session_obj.started_at or get_utc_now()
        await db.commit()

    # Wait for session init message
    try:
        init_message = await websocket.receive_text()
        init_data = json.loads(init_message)
        if init_data.get("type") != "session_start":
            raise ValueError("Expected session_start")
        interaction_mode = init_data.get("mode", "text")
    except Exception as e:
        logger.error(f"WebSocket init error: {e}")
        await websocket.close()
        return

    # Services
    whisper_service = WhisperService()
    audio_buffer = AudioBuffer()
    tts_service = TTSService()
    
    # Pre-warm Whisper model so first transcription doesn't take 190s
    if interaction_mode == "voice":
        logger.info("Warming up Whisper model...")
        try:
            await whisper_service.warmup()
            logger.info("Whisper model ready")
        except Exception as e:
            logger.warning(f"Whisper warmup failed (will retry on first transcription): {e}")
    
    # State tracking
    state = SessionState.WAITING_FOR_SPEECH
    pending_answer = None

    async def send_msg(msg: dict):
        """Called by Interviewer node (run_interview_graph)"""
        nonlocal state
        
        # intercept specific messages to handle TTS
        msg_type = msg.get("type")
        
        if msg_type == "question":
            state = SessionState.PLAYING_TTS
            # Send question text
            await websocket.send_json(msg)
            
            if interaction_mode == "voice":
                try:
                    await websocket.send_json({"type": "tts_start", "text": msg.get("text", "")})
                    async for chunk in tts_service.synthesize(msg.get("text", "")):
                        await websocket.send_bytes(b'\x01' + chunk)
                    await websocket.send_json({"type": "tts_end"})
                except Exception as e:
                    logger.error(f"TTS streaming error: {e}")
                    # ALWAYS send tts_end so frontend unmutes mic
                    try:
                        await websocket.send_json({"type": "tts_end"})
                    except:
                        pass
            
            # Back to waiting for user
            state = SessionState.WAITING_FOR_SPEECH
            audio_buffer.reset()
            logger.info("Now WAITING_FOR_SPEECH — mic should be active")
            
        elif msg_type == "anchor_change":
            await websocket.send_json({
                "type": "anchor_change",
                "anchor_title": msg.get("anchor_title", ""),
            })
            
        elif msg_type == "trigger_evaluation":
            # Fire and forget the Celery task
            from app.tasks.evaluate import evaluate_exchange_task
            exchange_id = msg.get("exchange_id")
            anchor = msg.get("anchor", {})
            interviewer_confidence = msg.get("interviewer_confidence", 3)
            if exchange_id:
                evaluate_exchange_task.delay(exchange_id, anchor, interviewer_confidence)
                logger.info(f"Queued evaluate_exchange_task for exchange {exchange_id}")
            # Do NOT send this message to the client!
            
        elif msg_type == "session_complete":
            await websocket.send_json(msg)
            session_obj.status = SessionStatus.completed
            session_obj.ended_at = get_utc_now()
            if recruiter_interview:
                recruiter_interview.status = SessionStatus.completed
            await db.commit()
            # Trigger report generation in background
            from app.tasks.report import generate_report_task
            generate_report_task.delay(str(session_id))
            logger.info(f"Queued generate_report_task for session {session_id}")
            
        else:
            # Send other messages verbatim
            await websocket.send_json(msg)

    async def process_binary(data: bytes):
        """Process incoming audio using AudioBuffer."""
        nonlocal state, pending_answer
        
        if state != SessionState.WAITING_FOR_SPEECH:
            return
            
        utterance = audio_buffer.add_chunk(data)
        if utterance:
            logger.info(f"End-of-speech detected! Utterance size: {len(utterance)} bytes")
            state = SessionState.PROCESSING_STT
            
            async def run_stt(audio_data):
                nonlocal state, pending_answer
                transcript = await whisper_service.transcribe(audio_data)
                logger.info(f"STT result: '{transcript}'")
                if transcript.strip():
                    pending_answer = transcript.strip()
                    await websocket.send_json({"type": "transcript", "text": pending_answer, "is_final": True})
                    await websocket.send_json({"type": "interviewer_thinking"})
                    state = SessionState.AGENT_THINKING
                else:
                    state = SessionState.WAITING_FOR_SPEECH
                    audio_buffer.reset()
            
            asyncio.create_task(run_stt(utterance))

    async def recv_msg() -> Dict[str, Any]:
        """
        Receives messages from WebSocket.
        Yields {"type": "answer", "text": transcript} when utterance complete.
        """
        nonlocal state, pending_answer
        
        while True:
            if pending_answer is not None:
                ans = pending_answer
                pending_answer = None
                return {"type": "answer", "text": ans}

            try:
                message = await websocket.receive()
                
                if "bytes" in message:
                    if interaction_mode == "voice":
                        await process_binary(message["bytes"])
                elif "text" in message:
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "answer" and interaction_mode == "text":
                            state = SessionState.AGENT_THINKING
                            await websocket.send_json({"type": "interviewer_thinking"})
                            return {"type": "answer", "text": data.get("text", "")}
                    except json.JSONDecodeError:
                        pass
                elif message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect()

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected")
                return {"type": "disconnect"}
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                await asyncio.sleep(0.1)

    # Trigger graph
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
