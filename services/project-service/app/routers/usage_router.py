from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db, LlmCallModel, AgentRunModel, AgentEventModel
from schemas import (
    LlmCallIngest, LlmCallResponse,
    AgentRunIngest, AgentRunResponse,
    AgentEventIngest, AgentEventResponse
)
from auth import get_current_user, get_current_admin, get_current_user_with_project_access
from sqlalchemy import desc

router = APIRouter(prefix="/api/usage", tags=["usage"])


# ---------------------- Ingest Endpoints (service token allowed) ----------------------
from fastapi import Header
from auth import oauth2_scheme
import os

SERVICE_TOKEN = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")

def require_service_or_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "")
    if token == SERVICE_TOKEN:
        return "service"
    # non-service token will be validated by downstream dependency in endpoints
    return "user"

@router.post("/llm-calls", response_model=LlmCallResponse)
async def ingest_llm_call(payload: LlmCallIngest, who=Depends(require_service_or_user), db: Session = Depends(get_db)):
    try:
        rec = LlmCallModel(
            project_id=payload.project_id,
            task_id=payload.task_id,
            correlation_id=payload.correlation_id,
            provider=payload.provider,
            model=payload.model,
            prompt=payload.prompt,
            response=payload.response,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            total_tokens=payload.total_tokens,
            cost_usd_cents=payload.cost_usd_cents,
            duration_ms=payload.duration_ms,
            status=payload.status or "success",
            error_message=payload.error_message,
            meta=payload.metadata,
            content_policy_applied=payload.content_policy_applied if payload.content_policy_applied is not None else True,
            truncated=payload.truncated if payload.truncated is not None else False,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to ingest llm call: {e}")

@router.post("/agent-runs", response_model=AgentRunResponse)
async def ingest_agent_run(payload: AgentRunIngest, who=Depends(require_service_or_user), db: Session = Depends(get_db)):
    try:
        rec = AgentRunModel(
            project_id=payload.project_id,
            correlation_id=payload.correlation_id,
            agent_type=payload.agent_type,
            task_name=payload.task_name,
            status=payload.status or "running",
            total_input_tokens=payload.total_input_tokens,
            total_output_tokens=payload.total_output_tokens,
            total_cost_usd_cents=payload.total_cost_usd_cents,
            duration_ms=payload.duration_ms,
            started_at=payload.started_at,
            completed_at=payload.completed_at,
            meta=payload.metadata,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to ingest agent run: {e}")

@router.post("/agent-events", response_model=AgentEventResponse)
async def ingest_agent_event(payload: AgentEventIngest, who=Depends(require_service_or_user), db: Session = Depends(get_db)):
    try:
        rec = AgentEventModel(
            run_id=payload.run_id,
            project_id=payload.project_id,
            correlation_id=payload.correlation_id,
            role=payload.role,
            event_type=payload.event_type,
            provider=payload.provider,
            model=payload.model,
            content=payload.content,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            total_tokens=payload.total_tokens,
            cost_usd_cents=payload.cost_usd_cents,
            meta=payload.metadata,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to ingest agent event: {e}")


# ---------------------- Query Endpoints (user auth + RBAC) ----------------------

@router.get("/llm-calls", response_model=List[LlmCallResponse])
async def list_llm_calls(
    project_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(LlmCallModel)
    if project_id:
        q = q.filter(LlmCallModel.project_id == project_id)
    if provider:
        q = q.filter(LlmCallModel.provider == provider)
    if model:
        q = q.filter(LlmCallModel.model == model)
    if correlation_id:
        q = q.filter(LlmCallModel.correlation_id == correlation_id)
    rows = q.order_by(desc(LlmCallModel.created_at)).offset(offset).limit(limit).all()
    return rows

@router.get("/agent-runs", response_model=List[AgentRunResponse])
async def list_agent_runs(
    project_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(AgentRunModel)
    if project_id:
        q = q.filter(AgentRunModel.project_id == project_id)
    if correlation_id:
        q = q.filter(AgentRunModel.correlation_id == correlation_id)
    rows = q.order_by(desc(AgentRunModel.started_at)).offset(offset).limit(limit).all()
    return rows

@router.get("/agent-events", response_model=List[AgentEventResponse])
async def list_agent_events(
    run_id: Optional[str] = None,
    project_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(AgentEventModel)
    if run_id:
        q = q.filter(AgentEventModel.run_id == run_id)
    if project_id:
        q = q.filter(AgentEventModel.project_id == project_id)
    if correlation_id:
        q = q.filter(AgentEventModel.correlation_id == correlation_id)
    rows = q.order_by(desc(AgentEventModel.created_at)).offset(offset).limit(limit).all()
    return rows
