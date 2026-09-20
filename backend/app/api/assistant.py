import uuid

from fastapi import APIRouter, HTTPException

from assistant.agent.graph import get_graph, pending_approval, resume, start
from backend.app.core.security import CurrentUser, create_access_token
from backend.app.schemas.models import (
    ApprovalRequest,
    ChatRequest,
    ChatResponse,
    PendingAction,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


def to_response(thread_id: str, result: dict) -> ChatResponse:
    request = pending_approval(result)
    if request is not None:
        return ChatResponse(
            thread_id=thread_id,
            awaiting_approval=True,
            reason=request["reason"],
            actions=[PendingAction(**action) for action in request["actions"]],
        )
    return ChatResponse(thread_id=thread_id, reply=result["messages"][-1].content)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, user: CurrentUser) -> ChatResponse:
    thread_id = payload.thread_id or f"{user.username}-{uuid.uuid4().hex[:12]}"
    token = create_access_token(user)
    try:
        result = start(payload.message, token=token, role=user.role, thread_id=thread_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant failed: {exc}") from exc
    return to_response(thread_id, result)


@router.post("/approve", response_model=ChatResponse)
def approve(payload: ApprovalRequest, user: CurrentUser) -> ChatResponse:
    config = {"configurable": {"thread_id": payload.thread_id}}
    snapshot = get_graph().get_state(config)
    if not snapshot.next:
        raise HTTPException(
            status_code=409, detail="This conversation has no action waiting for approval"
        )
    decisions = {
        d.action_id: {"approved": d.approved, "note": d.note or ""} for d in payload.decisions
    }
    try:
        result = resume(decisions, thread_id=payload.thread_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant failed: {exc}") from exc
    return to_response(payload.thread_id, result)
