"""Interface d'administration Django (usage technique).

Volontairement limitée : les projets, documents, segments et versions n'y figurent PAS, pour que le
contenu d'un projet confidentiel ne soit jamais visible par un autre compte (décision D3). Les clés
ne sont jamais affichées, même chiffrées.
"""
from django.contrib import admin

from .models import EngineSetting, Glossary, GlossaryEntry, TranslationJob


@admin.register(EngineSetting)
class EngineSettingAdmin(admin.ModelAdmin):
    list_display = ("user", "engine", "status", "last_tested_at", "enabled")
    exclude = ("encrypted_key",)


@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "engine", "status", "total_items", "chars_sent")
    list_filter = ("status", "engine", "kind")
    exclude = ("scope_label",)  # la portée peut citer le titre d'un projet confidentiel

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class GlossaryEntryInline(admin.TabularInline):
    model = GlossaryEntry
    extra = 0


@admin.register(Glossary)
class GlossaryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "source_lang", "target_lang", "version", "updated_at")
    inlines = [GlossaryEntryInline]
