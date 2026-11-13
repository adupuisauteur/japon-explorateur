from django.contrib import admin

from .models import ImportJob, IncomingRecord, SyncJob

for m in (ImportJob, IncomingRecord, SyncJob):
    admin.site.register(m)
