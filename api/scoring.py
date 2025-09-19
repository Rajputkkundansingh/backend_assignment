# api/scoring.py
from .models import Lead, Offer
import os
from dotenv import load_dotenv

# Try importing OpenAI and Google Gemini clients if installed.
try:
    from openai import OpenAI, OpenAIError
    HAS_OPENAI = True
except Exception:
    OpenAI = None
    OpenAIError = Exception
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except Exception:
    genai = None
    HAS_GEMINI = False

# Load .env (local dev). In production, use platform env vars.
load_dotenv()

# Environment-driven configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# USE_AI toggles whether to attempt a remote model at all. Useful for demos without keys.
USE_AI = os.getenv("USE_AI", "True").lower() in ("1", "true", "yes")
# PREFERRED_AI: "auto" (prefer Gemini if available), "openai", "gemini"
PREFERRED_AI = os.getenv("PREFERRED_AI", "auto").lower()

# Initialize clients if keys are present
openai_client = None
if HAS_OPENAI and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        openai_client = None

if HAS_GEMINI and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_client = genai
    except Exception:
        gemini_client = None
else:
    gemini_client = None


# ------------------------
# Rule Layer function
# ------------------------
def calculate_rule_score(lead, offer):
    """
    Rule based score (max 50):
      - Role relevance: decision maker (+20), influencer (+10), else 0
      - Industry match: exact ICP (+20), adjacent (+10), else 0
      - Data completeness: all fields present (+10)
    Returns: (score:int, reasoning:str)
    """
    score = 0
    reasoning = []

    # broadened lists for better coverage
    decision_makers = ["head", "ceo", "cto", "founder", "manager", "director", "vp", "vice president"]
    influencers = ["lead", "executive", "specialist", "analyst", "principal", "senior"]

    role_text = (lead.role or "").lower()
    if any(dm in role_text for dm in decision_makers):
        score += 20
        reasoning.append("Role is decision maker (+20)")
    elif any(inf in role_text for inf in influencers):
        score += 10
        reasoning.append("Role is influencer (+10)")
    else:
        reasoning.append("Role not relevant (+0)")

    matched_industries = [ic.lower() for ic in (offer.ideal_use_cases or [])]
    industry_text = (lead.industry or "").lower()
    if industry_text in matched_industries:
        score += 20
        reasoning.append("Industry matches ICP (+20)")
    else:
        score += 10
        reasoning.append("Industry adjacent (+10)")

    fields = [lead.name, lead.role, lead.company, lead.industry, lead.location, lead.linkedin_bio]
    if all(fields):
        score += 10
        reasoning.append("All fields present (+10)")
    else:
        reasoning.append("Missing some fields (+0)")

    return score, "; ".join(reasoning)


# ------------------------
# Deterministic fallback "AI" stub
# ------------------------
def simple_ai_stub(lead, offer):
    """
    A simple deterministic fallback that simulates an AI decision.
    Useful when external models are unavailable.
    Returns: (ai_points:int, intent:str, reasoning:str)
    """
    text = " ".join([
        (lead.role or ""),
        (lead.industry or ""),
        (lead.linkedin_bio or ""),
        " ".join(offer.ideal_use_cases or [])
    ]).lower()

    # Heuristics
    decision_keywords = ["ceo", "cto", "founder", "head", "director", "vp", "vice president"]
    influencer_keywords = ["lead", "manager", "senior", "principal", "marketing", "executive"]

    if any(k in text for k in decision_keywords):
        return 50, "High", "Role and context indicate a decision maker with high intent (fallback)."
    if any(k in text for k in influencer_keywords):
        return 30, "Medium", "Role and context indicate an influencer; moderate intent (fallback)."
    return 10, "Low", "No strong buying signals found (fallback)."


# ------------------------
# Provider-specific callers
# ------------------------
def _call_openai(lead, offer):
    """Call OpenAI chat completion and return text. Raises on errors."""
    prompt = _build_prompt(lead, offer)
    resp = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150
    )
    # Defensive extraction
    return getattr(resp.choices[0].message, "content", str(resp.choices[0]))


def _call_gemini(lead, offer):
    """Call Google Gemini (best-effort across genai versions) and return text."""
    prompt = _build_prompt(lead, offer)
    # Try the most common wrappers
    try:
        # newer google-generativeai style
        resp = genai.generate_text(model="gemini-1.5-flash", input=prompt)
        # response may expose .text or dict-like structure
        if hasattr(resp, "text"):
            return resp.text
        if isinstance(resp, dict):
            # attempt common structure
            return resp.get("candidates", [{}])[0].get("content", "") or str(resp)
        return str(resp)
    except Exception:
        try:
            # alternative API surface
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp2 = model.generate_content(prompt)
            return getattr(resp2, "text", str(resp2))
        except Exception as e:
            # re-raise so the caller knows Gemini failed
            raise e


def _build_prompt(lead, offer):
    """Create the prompt sent to the AI model."""
    return f"""
Lead Details:
Name: {lead.name}
Role: {lead.role}
Company: {lead.company}
Industry: {lead.industry}
Location: {lead.location}
LinkedIn Bio: {lead.linkedin_bio}

Offer Details:
Name: {offer.name}
Value Props: {', '.join(offer.value_props or [])}
Ideal Use Cases: {', '.join(offer.ideal_use_cases or [])}

Task:
Classify this lead's buying intent as High, Medium, or Low.
Give reasoning in 1–2 sentences.
Return only plain text explanation (no JSON required).
"""


# ------------------------
# AI Layer function (public)
# ------------------------
def calculate_ai_score(lead, offer):
    """
    Returns (ai_points:int, intent:str, ai_reasoning:str).
    Will try the preferred provider(s) and fall back to a deterministic stub
    if providers are unavailable or throw errors.
    Controlled by USE_AI and PREFERRED_AI env variables.
    """
    # If AI usage is disabled, immediately fallback
    if not USE_AI:
        return simple_ai_stub(lead, offer)

    # Helper to map text -> intent & points
    def map_text_to_intent(text):
        t = (text or "").lower()
        if "high" in t:
            return 50, "High"
        if "medium" in t:
            return 30, "Medium"
        if "low" in t:
            return 10, "Low"
        # catch words indicating high/medium/low
        if any(w in t for w in ["likely", "interested", "ready", "buy"]):
            return 50, "High"
        if any(w in t for w in ["consider", "maybe", "could", "possible"]):
            return 30, "Medium"
        return None, None

    # Decide provider order
    providers = []
    if PREFERRED_AI == "openai":
        providers = ["openai", "gemini"]
    elif PREFERRED_AI == "gemini":
        providers = ["gemini", "openai"]
    else:  # auto
        providers = ["gemini", "openai"]

    last_error = None
    for p in providers:
        try:
            if p == "openai" and openai_client:
                ai_text = _call_openai(lead, offer)
            elif p == "gemini" and gemini_client:
                ai_text = _call_gemini(lead, offer)
            else:
                continue  # provider not available
            ai_text = (ai_text or "").strip()
            ai_points, intent = map_text_to_intent(ai_text)
            if intent is None:
                # If model didn't explicitly say High/Medium/Low, try fallback analysis
                ai_points, intent, reasoning = simple_ai_stub(lead, offer)
                reasoning = f"{reasoning}; model output: {ai_text}"
                return ai_points, intent, reasoning
            return ai_points, intent, ai_text
        except Exception as e:
            last_error = e
            # try the next provider

    # If we reach here, no provider succeeded -> deterministic fallback with error attached
    ai_points, intent, reasoning = simple_ai_stub(lead, offer)
    err_msg = f"AI scoring failed: {type(last_error).__name__ if last_error else 'NoProvider'} - {str(last_error) if last_error else 'No provider available'}"
    reasoning = f"{reasoning}; {err_msg}"
    return ai_points, intent, reasoning
