import json
from pathlib import Path

from .dtw_comparator import compare_with_dtw
from .retriever import retrieve
from .llm_client import generate_coaching_feedback, generate_chat_response

async def process_form_feedback(move_id: str, user_landmark_frames: list) -> dict:
    """
    Main RAG orchestrator — DTW-based sequence comparison.

    Parameters
    ----------
    move_id              : e.g. 'mae_geri'
    user_landmark_frames : list of frames, each frame is a list of 33 dicts
                           [{"x":…,"y":…,"z":…,"visibility":…}, …×33]
                           (the user's full rep, typically 30 frames)

    Returns
    -------
    {
      "feedback": "<LLM coaching text>",
      "errors":   [{"joint":…, "mean_error":…, …}, …],
      "sources":  [{"text":…, "metadata":…}, …]
    }
    """

    # 1. DTW compare user sequence to Exemplar reference
    significant_errors = compare_with_dtw(move_id, user_landmark_frames)

    if not significant_errors:
        return {
            "feedback": (
                "Excellent! Your movement closely matches the master's form. "
                "Keep practising to build muscle memory!"
            ),
            "errors": [],
            "sources": [],
        }

    # 2. Retrieve coaching chunks for the top 2 worst joints
    all_chunks = []
    seen_texts = set()

    for err in significant_errors[:2]:
        query  = f"{move_id} {err['joint']} {err['query']}"
        chunks = retrieve(query, move=move_id, top_k=2)
        for ch in chunks:
            if ch["text"] not in seen_texts:
                seen_texts.add(ch["text"])
                all_chunks.append(ch)

    # 3. Generate LLM coaching feedback
    feedback_text = generate_coaching_feedback(move_id, significant_errors, all_chunks)

    return {
        "feedback": feedback_text,
        "errors":   significant_errors,
        "sources":  all_chunks,
    }


async def process_chat_message(message: str, move_id: str = None) -> dict:
    """Handle free-text chatbot queries using RAG context."""
    search_query = f"{move_id} {message}" if move_id else message
    chunks       = retrieve(search_query, move=move_id, top_k=3)
    response     = generate_chat_response(message, move_id or "General", chunks)
    return {"response": response, "sources": chunks}
