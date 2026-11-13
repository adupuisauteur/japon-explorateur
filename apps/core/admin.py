from django.contrib import admin

from .models import AppSettings, AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "target_type", "target_id", "summary")
    list_filter = ("action",)
    search_fields = ("summary", "target_id")

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(AppSettings)
