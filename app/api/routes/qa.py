import json
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, status, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.core import logger
from app.core.database import (
    save_conversation,
    add_conversation_message,
    get_conversation_messages,
    clear_conversation_messages,
    list_conversations,
)
from app.schemas.qa import (
    QARequest,
    QAResponse,
    ConversationMessageResponse,
    ConversationSummaryResponse,
)
from app.schemas.common import validate_query_param, ErrorResponse
from app.services.qa_service import (
    answer_question_with_gemini,
    answer_question_stream,
    generate_suggested_followups,
)

router = APIRouter(tags=["Q&A"])


@router.get(
    "/qa",
    response_model=QAResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def answer_question_get(
    question: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    response_length: Optional[str] = Query("short"),
    conversation_id: Optional[str] = Query(None),
):
    """Answer an educational question via GET query parameter with length control."""
    clean_q, err = validate_query_param(question, "question", max_length=5000)
    if err:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": err})

    clean_sub = None
    if subject is not None:
        clean_sub, s_err = validate_query_param(subject, "subject", max_length=100)
        if s_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": s_err})

    clean_diff = None
    if difficulty is not None:
        clean_diff, d_err = validate_query_param(difficulty, "difficulty", max_length=50)
        if d_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": d_err})
        if clean_diff.lower() not in ("beginner", "intermediate", "advanced", "standard"):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": "Difficulty must be one of: beginner, intermediate, advanced"})
        clean_diff = clean_diff.lower()

    clean_grade = None
    if grade_level is not None:
        clean_grade, g_err = validate_query_param(grade_level, "grade_level", max_length=50)
        if g_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": g_err})

    clean_lang = None
    if language is not None:
        clean_lang, l_err = validate_query_param(language, "language", max_length=30)
        if l_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": l_err})

    clean_len = "short"
    if response_length is not None:
        raw_len, len_err = validate_query_param(response_length, "response_length", max_length=30)
        if len_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": len_err})
        if raw_len and raw_len.lower() in ("short", "normal", "detailed"):
            clean_len = raw_len.lower()

    try:
        conv_id = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        history_turns = None
        if conversation_id:
            db_messages = await run_in_threadpool(get_conversation_messages, conversation_id, limit=8)
            if db_messages:
                history_turns = [{"role": m["role"], "content": m["content"]} for m in db_messages]

        answer = await run_in_threadpool(
            answer_question_with_gemini,
            clean_q,
            subject=clean_sub,
            difficulty=clean_diff,
            grade_level=clean_grade,
            language=clean_lang,
            response_length=clean_len,
            history=history_turns,
        )

        # Persist conversation turns in background threadpool
        await run_in_threadpool(save_conversation, conv_id, clean_q[:50], "default", clean_sub, clean_diff, clean_grade, clean_lang or "english")
        await run_in_threadpool(add_conversation_message, conv_id, "user", clean_q)
        await run_in_threadpool(add_conversation_message, conv_id, "assistant", answer)

        adapted = bool(
            clean_sub
            or (clean_diff and clean_diff != "standard")
            or clean_grade
            or (clean_lang and clean_lang != "english")
            or (clean_len and clean_len != "short")
        )
        followups = generate_suggested_followups(clean_q, answer)

        return {
            "answer": answer,
            "conversation_id": conv_id,
            "subject": clean_sub,
            "difficulty": clean_diff,
            "grade_level": clean_grade,
            "language": clean_lang,
            "response_length": clean_len,
            "adapted": adapted,
            "suggested_followups": followups,
        }
    except Exception as exc:
        logger.error("Error in /qa (GET): %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while generating the answer."}
        )


@router.post(
    "/qa",
    response_model=QAResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def answer_question_post(payload: QARequest):
    """Answer an educational question via JSON POST request with multi-turn and length support."""
    try:
        conv_id = payload.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

        # Resolve conversation history
        history_dicts = None
        if payload.history is not None and len(payload.history) > 0:
            history_dicts = [{"role": t.role, "content": t.content} for t in payload.history]
        elif payload.conversation_id:
            # Query isolated session history from database
            db_messages = await run_in_threadpool(get_conversation_messages, payload.conversation_id, limit=8)
            if db_messages:
                history_dicts = [{"role": m["role"], "content": m["content"]} for m in db_messages]

        resp_len = payload.response_length or "short"
        answer = await run_in_threadpool(
            answer_question_with_gemini,
            payload.question,
            subject=payload.subject,
            difficulty=payload.difficulty,
            grade_level=payload.grade_level,
            language=payload.language,
            explanation_style=payload.explanation_style,
            response_length=resp_len,
            history=history_dicts,
        )

        # Persist conversation message turns
        try:
            await run_in_threadpool(
                save_conversation,
                conv_id,
                payload.question[:50],
                "default",
                payload.subject,
                payload.difficulty,
                payload.grade_level,
                payload.language or "english",
            )
            await run_in_threadpool(add_conversation_message, conv_id, "user", payload.question)
            await run_in_threadpool(add_conversation_message, conv_id, "assistant", answer)
        except Exception as db_err:
            logger.warning("Could not persist conversation message: %s", type(db_err).__name__)

        adapted = bool(
            payload.subject
            or (payload.difficulty and payload.difficulty != "standard")
            or payload.grade_level
            or (payload.language and payload.language != "english")
            or payload.explanation_style
            or (resp_len != "short")
        )
        followups = generate_suggested_followups(payload.question, answer)

        return {
            "answer": answer,
            "conversation_id": conv_id,
            "subject": payload.subject,
            "difficulty": payload.difficulty,
            "grade_level": payload.grade_level,
            "language": payload.language,
            "response_length": resp_len,
            "adapted": adapted,
            "suggested_followups": followups,
        }
    except Exception as exc:
        logger.error("Error in /qa (POST): %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while generating the answer."}
        )


@router.post("/qa/stream")
async def answer_question_stream_endpoint(payload: QARequest):
    """
    Streams progressive AI response chunks using Server-Sent Events (SSE).
    Supports multi-turn history, session isolation, answer-length control, and graceful non-streaming fallback.
    """
    conv_id = payload.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

    # Resolve conversation history
    history_dicts = None
    if payload.history is not None and len(payload.history) > 0:
        history_dicts = [{"role": t.role, "content": t.content} for t in payload.history]
    elif payload.conversation_id:
        db_messages = await run_in_threadpool(get_conversation_messages, payload.conversation_id, limit=8)
        if db_messages:
            history_dicts = [{"role": m["role"], "content": m["content"]} for m in db_messages]

    resp_len = payload.response_length or "short"

    def event_stream():
        accumulated = []
        try:
            for chunk in answer_question_stream(
                payload.question,
                subject=payload.subject,
                difficulty=payload.difficulty,
                grade_level=payload.grade_level,
                language=payload.language,
                explanation_style=payload.explanation_style,
                response_length=resp_len,
                history=history_dicts,
            ):
                if chunk:
                    accumulated.append(chunk)
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            full_answer = "".join(accumulated).strip()
            # Persist turns
            try:
                save_conversation(
                    conv_id,
                    payload.question[:50],
                    "default",
                    payload.subject,
                    payload.difficulty,
                    payload.grade_level,
                    payload.language or "english"
                )
                add_conversation_message(conv_id, "user", payload.question)
                add_conversation_message(conv_id, "assistant", full_answer)
            except Exception as e:
                logger.debug("Failed saving streamed turns: %s", e)

            followups = generate_suggested_followups(payload.question, full_answer)
            yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id, 'response_length': resp_len, 'suggested_followups': followups})}\n\n"
        except Exception as exc:
            logger.error("Error during streaming SSE: %s", type(exc).__name__)
            yield f"data: {json.dumps({'error': 'Error generating streaming response.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/qa/new-chat")
async def start_new_chat(
    subject: Optional[str] = None,
    grade_level: Optional[str] = None,
    language: Optional[str] = "english"
):
    """Generates a fresh conversation session ID to isolate student chat contexts."""
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    await run_in_threadpool(
        save_conversation,
        conv_id,
        "New Learning Session",
        "default",
        subject,
        None,
        grade_level,
        language
    )
    return {"conversation_id": conv_id, "status": "created", "title": "New Learning Session"}


@router.get("/qa/conversations", response_model=List[ConversationSummaryResponse])
async def get_recent_conversations(limit: int = 15):
    """Lists recent conversations within the workspace."""
    conversations = await run_in_threadpool(list_conversations, "default", limit)
    return conversations


@router.get("/qa/conversations/{conversation_id}", response_model=List[ConversationMessageResponse])
async def get_conversation_history(conversation_id: str, limit: int = 20):
    """Retrieves ordered messages for a specific conversation session."""
    messages = await run_in_threadpool(get_conversation_messages, conversation_id, limit)
    return messages


@router.delete("/qa/conversations/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """Clears messages for a specific conversation session."""
    success = await run_in_threadpool(clear_conversation_messages, conversation_id)
    return {"status": "cleared", "conversation_id": conversation_id, "success": success}
