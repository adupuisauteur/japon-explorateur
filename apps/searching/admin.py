from django.contrib import admin

from .models import ResultDecision, SavedSearch, SearchResult, SearchSession

for m in (SavedSearch, SearchSession, SearchResult, ResultDecision):
    admin.site.register(m)
