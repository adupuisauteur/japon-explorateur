from django.contrib import admin

from .models import ExportFile, ExportJob, ExportProfile

for m in (ExportFile, ExportJob, ExportProfile):
    admin.site.register(m)
