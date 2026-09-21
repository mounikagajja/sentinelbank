"""Server-sent events stream of live fraud scores."""

import json
import uuid

from confluent_kafka import Consumer
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.app.core.config import get_settings
from backend.app.core.security import get_current_user

settings = get_settings()
router = APIRouter(prefix="/stream", tags=["stream"])


def score_events():
    consumer = Consumer(
        {
            "bootstrap.servers": settings.redpanda_broker,
            "group.id": f"live-feed-{uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.scores_topic])
    try:
        yield ": connected\n\n"
        while True:
            message = consumer.poll(1.0)
            if message is None or message.error():
                yield ": keepalive\n\n"
                continue
            event = json.loads(message.value().decode("utf-8"))
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        consumer.close()


@router.get("/scores")
def stream_scores(token: str = Query(...)) -> StreamingResponse:
    try:
        get_current_user(token)
    except HTTPException:
        raise
    return StreamingResponse(
        score_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
