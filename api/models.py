from django.db import models

class Offer(models.Model):
    name = models.CharField(max_length=255)
    value_props = models.JSONField()  # store list
    ideal_use_cases = models.JSONField()  # store list
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Lead(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    industry = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    linkedin_bio = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
class LeadScore(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE)
    intent = models.CharField(max_length=10)
    score = models.IntegerField()
    reasoning = models.TextField()
    scored_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.name} - {self.intent}"
