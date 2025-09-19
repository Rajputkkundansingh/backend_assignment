from .models import Lead, Offer
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Use the new OpenAI client

# ------------------------
# Rule Layer function
# ------------------------
def calculate_rule_score(lead, offer):
    score = 0
    reasoning = []

    decision_makers = ["Head", "CEO", "Founder", "Manager", "Director"]
    influencers = ["Lead", "Executive", "Specialist", "Analyst"]

    if any(dm.lower() in lead.role.lower() for dm in decision_makers):
        score += 20
        reasoning.append("Role is decision maker (+20)")
    elif any(inf.lower() in lead.role.lower() for inf in influencers):
        score += 10
        reasoning.append("Role is influencer (+10)")
    else:
        reasoning.append("Role not relevant (+0)")

    matched_industries = [ic.lower() for ic in offer.ideal_use_cases]
    if lead.industry.lower() in matched_industries:
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
# AI Layer function
# ------------------------
def calculate_ai_score(lead, offer):
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
Give reasoning in 1-2 sentences.
"""

    # Using new API style
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150
    )

    ai_reasoning = response.choices[0].message.content.strip()

    if "High" in ai_reasoning:
        ai_points = 50
        intent = "High"
    elif "Medium" in ai_reasoning:
        ai_points = 30
        intent = "Medium"
    else:
        ai_points = 10
        intent = "Low"

    return ai_points, intent, ai_reasoning
