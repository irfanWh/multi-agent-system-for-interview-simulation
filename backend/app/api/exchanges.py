import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_db, get_current_user
from app.models.orm import Exchange, Session, User
from app.models.schemas import ExchangeResponse

router = APIRouter()

@router.get("/sessions/{session_id}/exchanges", response_model=List[ExchangeResponse])
async def get_session_exchanges(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Return all Q&A turns for a specific session.
    """
    # Verify session ownership
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id, 
            Session.user_id == current_user.id
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Fetch exchanges
    results = await db.execute(
        select(Exchange)
        .where(Exchange.session_id == session_id)
        .order_by(Exchange.turn_number)
    )
    
    return results.scalars().all()
