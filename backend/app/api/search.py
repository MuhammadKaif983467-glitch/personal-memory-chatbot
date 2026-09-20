"""Unified search + conversation analysis endpoints (read‑only analytics).

POST /search               -> unified search across messages, memories, conversations
GET /conversations/{id}/analysis  -> deterministic conversation analysis (topics, decisions, plans, commitments)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppContext, get_context, get_db
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import SearchRequest, SearchResponse, ConversationAnalysisOut

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def unified_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
) -> SearchResponse:
    """Search messages, memories and conversations across the project / person scope."""
    analytics = AnalyticsService(db)
    return analytics.search(
        query=request.query,
        project_id=request.project_id,
        person_id=request.person_id,
        conversation_id=request.conversation_id,
        date_from=request.date_from,
        date_to=request.date_to,
        memory_type=request.memory_type,
        status=request.status,
        limit=request.limit,
    )


@router.get(
    "/conversations/{conversation_id}/analysis",
    response_model=ConversationAnalysisOut,
)
def conversation_analysis(
    conversation_id: int,
    db: Session = Depends(get_db),
    context: AppContext = Depends(get_context),
) -> ConversationAnalysisOut:
    """Deterministic conversation analysis (topics, cues) — offline, no AI needed."""
    analytics = AnalyticsService(db)
    return analytics.analyze_conversation(conversation_id)