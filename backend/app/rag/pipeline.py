import json
from pathlib import Path

from .dtw_comparator import compare_with_dtw
from .retriever import retrieve
from .llm_client import generate_coaching_feedback, generate_chat_response

async def process_form_feedback(
    move_id: str,
    user_landmark_frames: list,
    session_id: int | None = None,
    move_reference_id: int | None = None,
    confidence: float | None = None,
) -> dict:
    """
    Main RAG orchestrator — DTW-based sequence comparison.

    Parameters
    ----------
    move_id              : e.g. 'mae_geri'
    user_landmark_frames : list of frames, each frame is a list of 33 dicts
                           [{x,y,z,visibility}, …×33]
    session_id           : optional — if provided, errors are saved to detection table
    move_reference_id    : optional — FK for detection table
    confidence           : optional — model confidence for detection table

    Returns
    -------
    {
      "feedback": "<LLM coaching text>",
      "errors":   [{joint, mean_error, status, …}, …],
      "sources":  [{text, metadata}, …]
    }
    """

    # 1. DTW compare user sequence to reference (MADS P3 or exemplar fallback)
    significant_errors = compare_with_dtw(move_id, user_landmark_frames)

    # 2. Persist errors to Detection table immediately (non-blocking path)
    if session_id is not None and significant_errors:
        _save_detection_errors(
            session_id=session_id,
            move_reference_id=move_reference_id,
            confidence=confidence,
            errors=significant_errors,
        )

    if not significant_errors:
        return {
            "feedback": (
                "Excellent! Your movement closely matches the master's form. "
                "Keep practising to build muscle memory!"
            ),
            "errors": [],
            "sources": [],
        }

    # 3. Retrieve coaching chunks for the top 2 worst joints
    all_chunks = []
    seen_texts = set()

    for err in significant_errors[:2]:
        query  = f"{move_id} {err['joint']} {err['query']}"
        chunks = retrieve(query, move=move_id, top_k=2)
        for ch in chunks:
            if ch["text"] not in seen_texts:
                seen_texts.add(ch["text"])
                all_chunks.append(ch)

    # 4. Generate LLM coaching feedback
    feedback_text = generate_coaching_feedback(move_id, significant_errors, all_chunks)

    return {
        "feedback": feedback_text,
        "errors":   significant_errors,
        "sources":  all_chunks,
    }


def _save_detection_errors(
    session_id: int,
    move_reference_id: int | None,
    confidence: float | None,
    errors: list[dict],
) -> None:
    """
    Persist DTW correction errors to the detection table.
    Called synchronously but in a background-safe way.
    """
    try:
        from app.database import SessionLocal
        from app.models.session import Detection
        import time

        db = SessionLocal()
        try:
            det = Detection(
                session_id        = session_id,
                move_reference_id = move_reference_id,
                confidence        = confidence,
                corrections       = errors,   # JSONB column
                frame_timestamp   = time.time(),
            )
            db.add(det)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        # Never crash the feedback pipeline over a DB write failure
        print(f"[pipeline] ⚠️  Detection save failed: {exc}")


async def process_chat_message(message: str, move_id: str = None) -> dict:
    """Handle free-text chatbot queries using RAG context."""
    search_query = f"{move_id} {message}" if move_id else message
    chunks       = retrieve(search_query, move=move_id, top_k=3)
    response     = generate_chat_response(message, move_id or "General", chunks)
    return {"response": response, "sources": chunks}
