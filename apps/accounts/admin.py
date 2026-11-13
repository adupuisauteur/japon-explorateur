from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class AppUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Application", {"fields": ("role", "display_name", "default_search_mode")}),)
    list_display = ("username", "display_name", "role", "is_active", "last_login")
