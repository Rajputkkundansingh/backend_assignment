# scoring.py (update)
import os
from openai import OpenAI, OpenAIError

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_AI = os.getenv("USE_AI", "True").lower() in ("1", "true", "yes")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None

def simple_ai_stub(lead, offer):
    """Deterministic fallback: classify based on keywords & role heuristics."""
    text = " ".join([lead.role, lead.industry, lead.linkedin_bio or ""]).lower()
    # simple heuristics:
    if any(k in text for k in ["ceo", "cto", "founder", "head", "director", "vp"]):
        intent = "High"
        ai_points = 50
        reasoning = "Role indicates decision maker; high buying intent based on role keywords."
    elif any(k in text for k in ["lead", "manager", "principal", "senior", "marketing"]):
        intent = "Medium"
        ai_points = 30
        reasoning = "Role indicates influencer; moderate buying intent."
    else:
        intent = "Low"
        ai_points = 10
        reasoning = "No decision-making signals found; low buying intent."
    return ai_points, intent, reasoning

def calculate_ai_score(lead, offer):
    """
    Attempts to call OpenAI. If not available, or quota fails, falls back to simple_ai_stub.
    Returns: (ai_points:int, intent:str, ai_reasoning:str)
    """
    if not USE_AI or client is None:
        return simple_ai_stub(lead, offer)

    prompt = f"""
Lead Details:
Name: {lead.name}
Role: {lead.role}
Company: {lead.company}
Industry: {lead.industry}
Location: {lead.location}
LinkedIn Bio: {lead.linkedin_bio}

Offer Details:
Name: {offer.name}
Value Props: {', '.join(offer.value_props)}
Ideal Use Cases: {', '.join(offer.ideal_use_cases)}

Task:
Classify this lead's buying intent as High, Medium, or Low.
Give reasoning in 1–2 sentences.
"""

    try:
        # current usage in your codebase used client.chat.completions.create
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150
        )
        ai_text = response.choices[0].message.content.strip()

        # map AI text to points
        if "high" in ai_text.lower():
            return 50, "High", ai_text
        if "medium" in ai_text.lower():
            return 30, "Medium", ai_text
        if "low" in ai_text.lower():
            return 10, "Low", ai_text

        # fallback mapping if AI didn't reply exactly
        if any(w in ai_text.lower() for w in ["interested", "ready", "likely"]):
            return 50, "High", ai_text
        if any(w in ai_text.lower() for w in ["consider", "could", "maybe"]):
            return 30, "Medium", ai_text

        # if unknown mapping, return fallback
        return simple_ai_stub(lead, offer)
    except OpenAIError as e:
        # log the error somewhere if you have logging
        err_str = f"AI scoring failed: {type(e).__name__} - {str(e)}"
        # return fallback but include error message in reasoning
        ai_points, intent, reasoning = simple_ai_stub(lead, offer)
        reasoning = f"{reasoning}; AI scoring failed: {err_str}"
        return ai_points, intent, reasoning
    except Exception as e:
        ai_points, intent, reasoning = simple_ai_stub(lead, offer)
        reasoning = f"{reasoning}; AI scoring failed: {str(e)}"
        return ai_points, intent, reasoning
