import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env', override=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Lazy-initialize client so startup never crashes even if key is missing
_groq_client = None

def _get_client():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            print(f"[llm_client] Groq client init failed: {e}")
    return _groq_client


# ── Fallback formatter (used when Groq is unavailable) ────────────────────────
def _fallback_coaching(move_name: str, error_context: list) -> str:
    """
    Returns plain-text coaching from the DTW error list without calling Groq.
    This always works — it's just less naturally phrased than the LLM version.
    """
    if not error_context:
        return "Looking good! Keep practising this technique."

    lines = [f"📊 Form analysis for **{move_name.replace('_', ' ').title()}**:\n"]
    for err in error_context[:3]:
        joint = err["joint"].replace("_", " ").title()
        diff  = err["mean_error"]
        uval  = err["user_val"]
        rval  = err["ref_val"]
        direction = "too extended" if uval > rval else "needs more extension"
        lines.append(f"• **{joint}**: {direction} (you: {uval:.0f}° | master: {rval:.0f}°, diff {diff:.0f}°)")

    lines.append(
        "\n💡 Focus on matching the master's posture in those joints. "
        "Try slowing down the movement and checking each position in a mirror."
    )
    return "\n".join(lines)


# ── Coaching feedback ──────────────────────────────────────────────────────────
def generate_coaching_feedback(move_name: str, error_context: list, retrieved_chunks: list) -> str:
    client = _get_client()

    if not client:
        print("[llm_client] Groq key missing or client failed — using fallback coaching.")
        return _fallback_coaching(move_name, error_context)

    error_summary = "\n".join([
        f"- {e['joint']}: {e['query']} (user: {round(e['user_val'])}°, target: {e['target_range']}°)"
        for e in error_context
    ])
    knowledge_summary = "\n\n".join([
        f"Source {i+1}:\n{chunk['text']}"
        for i, chunk in enumerate(retrieved_chunks)
    ])

    prompt = f"""You are an encouraging and expert AI Karate Sensei.

The student just attempted a '{move_name}'. Here are the specific errors detected by our computer vision system:
{error_summary}

Here is coaching knowledge retrieved from the master database regarding these issues:
{knowledge_summary}

Your task:
Write a friendly, encouraging, and actionable response strictly based on the coaching knowledge provided.
- Limit to 2-3 short paragraphs.
- Be encouraging ("Great effort!").
- Give them 1-2 specific actions to fix their errors.
- Never mention "computer vision", "angles", or "degrees" — translate the math into physical feelings
  (e.g. "tuck your elbow tighter", "extend your leg fully").
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful and expert AI Karate coach."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[llm_client] Groq API error: {type(e).__name__}: {e}")
        print("[llm_client] Falling back to plain-text coaching.")
        return _fallback_coaching(move_name, error_context)



# ── RAG-only chat fallback ─────────────────────────────────────────────────────
def _rag_only_chat_fallback(chat_message: str, retrieved_chunks: list) -> str:
    """Format retrieved coaching chunks as plain text when Groq is unavailable."""
    if not retrieved_chunks:
        return (
            "💡 I don't have specific knowledge about that topic yet.\n"
            "Try asking about mae geri, gyaku zuki, or gedan barai technique."
        )
    lines = ["💡 Here's what I know about your question:\n"]
    for i, chunk in enumerate(retrieved_chunks[:3], 1):
        lines.append(f"{i}. {chunk['text'].strip()}")
    lines.append(
        "\n_(AI coaching brain is currently offline — showing knowledge base directly)_"
    )
    return "\n\n".join(lines)


# ── Chat response ──────────────────────────────────────────────────────────────
def generate_chat_response(chat_message: str, move_name: str, retrieved_chunks: list) -> str:
    client = _get_client()

    if not client:
        print("[llm_client] Groq unavailable — using RAG-only chat fallback.")
        return _rag_only_chat_fallback(chat_message, retrieved_chunks)

    knowledge_summary = "\n\n".join([
        f"Source {i+1}:\n{chunk['text']}"
        for i, chunk in enumerate(retrieved_chunks)
    ])

    prompt = f"""You are an encouraging and expert AI Karate Sensei answering a student's question.

Context (Move): {move_name}
Student asks: "{chat_message}"

Here is coaching knowledge retrieved from the master database:
{knowledge_summary}

Answer the student's question concisely using the provided knowledge. Be friendly and instructional.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful and expert AI Karate coach."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[llm_client] Groq chat error: {type(e).__name__}: {e}")
        return _rag_only_chat_fallback(chat_message, retrieved_chunks)
