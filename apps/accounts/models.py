from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Compte utilisateur. Les rôles sont prévus dès la V1 (§13)."""

    ROLE_ADMIN = "admin"
    ROLE_RESEARCHER = "researcher"
    ROLE_READER = "reader"
    ROLES = [
        (ROLE_ADMIN, "Administrateur"),
        (ROLE_RESEARCHER, "Chercheur"),
        (ROLE_READER, "Lecteur"),
    ]

    role = models.CharField("Rôle", max_length=20, choices=ROLES, default=ROLE_RESEARCHER)
    display_name = models.CharField("Nom affiché", max_length=150, blank=True)
    default_search_mode = models.CharField(
        "Mode d'enregistrement préféré", max_length=20, blank=True,
        choices=[("", "Réglage de l'instance"), ("auto", "Automatique"),
                 ("selective", "Sélectif"), ("manual", "Manuel / temporaire")],
    )
    preferred_sources = models.JSONField("Catalogues interrogés par défaut", default=list, blank=True)

    class Meta:
        verbose_name = "Utilisateur"

    def __str__(self):
        return self.display_name or self.get_full_name() or self.username

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def can_edit(self):
        """Chercheurs et administrateurs peuvent créer bibliothèque, dossiers et annotations."""
        return self.role in (self.ROLE_ADMIN, self.ROLE_RESEARCHER) or self.is_superuser

    def effective_search_mode(self):
        if self.default_search_mode:
            return self.default_search_mode
        from apps.core.models import AppSettings

        return AppSettings.get().default_search_mode
