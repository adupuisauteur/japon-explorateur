from django.contrib import admin

from . import models

for m in (models.Tag, models.LibraryEntry, models.Collection, models.CollectionShare, models.CollectionSection,
          models.CollectionRecord, models.Annotation, models.CorrectionProposal):
    admin.site.register(m)
