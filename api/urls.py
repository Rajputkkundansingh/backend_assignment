from django.urls import path
from .views import GetResultsView, OfferView, LeadUploadView, ScoreLeadsView

urlpatterns = [
    path('offer/', OfferView.as_view(), name='offer'),
    path('leads/upload/', LeadUploadView.as_view(), name='lead-upload'),
    path('score/', ScoreLeadsView.as_view(), name='score-leads'),
    path('results/<int:offer_id>/', GetResultsView.as_view(), name='get-results'),
]
