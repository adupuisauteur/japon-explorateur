from django.contrib import admin

from . import models


@admin.register(models.Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("record_id", "original_title", "catalogue", "source_id", "record_status", "version", "collected_at")
    list_filter = ("catalogue", "record_status", "period", "document_type")
    search_fields = ("record_id", "source_id", "original_title", "reading", "creator_original")
    readonly_fields = ("record_id", "raw_data", "record_hash", "version", "search_text", "normalization_log")


@admin.register(models.Catalogue)
class CatalogueAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "connector", "status", "enabled_for_search", "frequency", "last_success_at")


for m in (models.Institution, models.Creator, models.CreatorVariant, models.Work, models.Edition, models.Copy,
          models.RecordVersion, models.EditorialContent, models.Subject, models.RecordSubject, models.RecordLink,
          models.StoredFile):
    admin.site.register(m)
