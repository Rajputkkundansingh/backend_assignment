# scoring.py
import os
from google.ai import generativelanguage as gl
from google.api_core.exceptions import GoogleAPIError

# Initialize Google Generative AI client
client = gl.TextServiceClient()

def calculate_ai_score(lead, offer):
    """
    Calls Google Generative AI to score a lead for a given offer.
    Returns: points (int), intent (str), reasoning (str)
    """
    prompt = f"""
    Lead: {lead.name}, {lead.role}, {lead.company}, {lead.industry}, {lead.location}, {lead.linkedin_bio}
    Offer: {offer.title}, {offer.description}

    Score this lead for the offer from 0-50 points.
    Return JSON like: {{ "points": <int>, "intent": "<Low|Medium|High>", "reasoning": "<explanation>" }}
    """

    try:
        response = client.generate_text(
            model="models/text-bison-001",
            prompt=prompt,
            temperature=0.2,
            max_output_tokens=500
        )
        # Google returns a string, parse JSON safely
        import json
        output_text = response.candidates[0].content
        result = json.loads(output_text)
        return result.get("points", 0), result.get("intent", "Unknown"), result.get("reasoning", "")
    except (GoogleAPIError, ValueError, json.JSONDecodeError) as e:
        # Fallback if API fails
        return 0, "Unknown", f"AI scoring failed: {str(e)}"
