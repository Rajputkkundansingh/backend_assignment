import csv
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import LeadScore, Offer, Lead
from .serializers import OfferSerializer, LeadSerializer
import pandas as pd
from .scoring import calculate_rule_score, calculate_ai_score
from openai import OpenAIError



# -------------------------
# Offer CRUD
# -------------------------
class OfferView(APIView):
    def post(self, request):
        serializer = OfferSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Offer saved successfully", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# -------------------------
# Lead Upload
# -------------------------
class LeadUploadView(APIView):
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        df = pd.read_csv(file)
        leads_created = []

        for _, row in df.iterrows():
            lead_data = {
                "name": row.get("name", ""),
                "role": row.get("role", ""),
                "company": row.get("company", ""),
                "industry": row.get("industry", ""),
                "location": row.get("location", ""),
                "linkedin_bio": row.get("linkedin_bio", ""),
            }
            serializer = LeadSerializer(data=lead_data)
            if serializer.is_valid():
                serializer.save()
                leads_created.append(serializer.data)

        return Response(
            {"message": "Leads uploaded successfully", "data": leads_created},
            status=status.HTTP_201_CREATED,
        )

# -------------------------
# Score Leads
# -------------------------
class ScoreLeadsView(APIView):
    def post(self, request):
        offer_id = request.data.get("offer_id")
        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return Response({"error": "Offer not found"}, status=status.HTTP_404_NOT_FOUND)

        leads = Lead.objects.all()
        results = []

        # Clear previous scores
        LeadScore.objects.filter(offer=offer).delete()

        for lead in leads:
            # Rule-based scoring
            rule_score, rule_reasoning = calculate_rule_score(lead, offer)

            # AI-based scoring with safe error handling
            try:
                ai_points, intent, ai_reasoning = calculate_ai_score(lead, offer)
            except OpenAIError as e:
                ai_points, intent, ai_reasoning = 0, "Unknown", f"AI scoring failed: {str(e)}"

            final_score = rule_score + ai_points

            # Save result
            lead_score = LeadScore.objects.create(
                lead=lead,
                offer=offer,
                intent=intent,
                score=final_score,
                reasoning=f"{rule_reasoning}; {ai_reasoning}",
            )

            results.append({
                "name": lead.name,
                "role": lead.role,
                "company": lead.company,
                "intent": intent,
                "score": final_score,
                "reasoning": lead_score.reasoning,
            })

        return Response(results, status=status.HTTP_200_OK)

# -------------------------
# Get Results
# -------------------------
class GetResultsView(APIView):
    def get(self, request, offer_id=None):
        if not offer_id:
            return Response({"error": "offer_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return Response({"error": "Offer not found"}, status=status.HTTP_404_NOT_FOUND)

        scores = LeadScore.objects.filter(offer=offer)

        # CSV export
        if request.GET.get("export") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="lead_scores_offer_{offer_id}.csv"'
            writer = csv.writer(response)
            writer.writerow(["name", "role", "company", "intent", "score", "reasoning"])
            for s in scores:
                writer.writerow([s.lead.name, s.lead.role, s.lead.company, s.intent, s.score, s.reasoning])
            return response

        # Default JSON response
        results = [
            {
                "name": s.lead.name,
                "role": s.lead.role,
                "company": s.lead.company,
                "intent": s.intent,
                "score": s.score,
                "reasoning": s.reasoning,
            }
            for s in scores
        ]

        return Response(results, status=status.HTTP_200_OK)
