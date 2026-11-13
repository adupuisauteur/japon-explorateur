from django.contrib import admin

from .models import Incident, IncidentEvent, IncidentOccurrence


class OccurrenceInline(admin.TabularInline):
    model = IncidentOccurrence
    extra = 0
    readonly_fields = ["occurred_at", "app_version", "request_id", "http_status", "operation", "message"]
    exclude = ["context"]
    can_delete = False


class EventInline(admin.TabularInline):
    model = IncidentEvent
    extra = 0
    readonly_fields = ["at", "kind", "from_status", "to_status", "comment", "app_version", "user"]
    can_delete = False


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["uid", "title", "module", "source_code", "severity", "status", "occurrence_count", "last_seen_at"]
    list_filter = ["module", "severity", "status", "category", "is_manual"]
    search_fields = ["uid", "title", "message", "last_request_id"]
    readonly_fields = ["uid", "fingerprint", "first_seen_at", "last_seen_at", "occurrence_count",
                       "first_seen_version", "last_seen_version", "reappeared_count"]
    inlines = [EventInline, OccurrenceInline]
