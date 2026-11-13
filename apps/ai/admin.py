from django.contrib import admin

from .models import AIModelPrice, AIPreferenceProfile, AIProviderCredential, AITask


@admin.register(AIProviderCredential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "status", "last_tested_at")
    exclude = ("encrypted_key",)  # jamais affichée, même chiffrée


for m in (AIModelPrice, AIPreferenceProfile, AITask):
    admin.site.register(m)
