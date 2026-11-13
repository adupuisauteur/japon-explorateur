"""
Compte anonymisé ou supprimé : ses projets et glossaires de traduction sont confiés à un administrateur.

Décision du 13 novembre 2026 : ils ne sont jamais supprimés avec le compte. Les réglages de moteurs
et les clés, personnels, sont effacés. S'il n'existe aucun autre administrateur actif, l'opération
est refusée (TransferImpossible), et rien n'est modifié.

Deux chemins y mènent :
- l'anonymisation depuis Administration → Comptes (apps.accounts.views.user_anonymize), qui est la
  seule « suppression » proposée par l'application ;
- une suppression réelle de la ligne utilisateur (interface d'administration Django, script) :
  signal pre_delete. Le lien « propriétaire » n'ayant pas de cascade, une suppression qui
  contournerait ce signal est de toute façon refusée par la base (clé étrangère).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone


class TransferImpossible(Exception):
    """Aucun autre administrateur actif ne peut recevoir les projets et glossaires du compte."""


def owned_counts(user):
    return user.translation_projects.count(), user.translation_glossaries.count()


def pick_recipient(user):
    User = get_user_model()
    return (User.objects.filter(Q(role=User.ROLE_ADMIN) | Q(is_superuser=True), is_active=True)
            .exclude(pk=user.pk).order_by("pk").first())


@transaction.atomic
def release_user_translation_data(user, recipient=None):
    """Transfère projets et glossaires, efface réglages et clés. Retourne (destinataire, nb projets, nb glossaires)."""
    from .models import EngineSetting, Glossary, TranslationPreference, TranslationProject

    projects, glossaries = owned_counts(user)
    target = None
    if projects or glossaries:
        target = recipient or pick_recipient(user)
        if target is not None and not (target.is_active and target.is_admin_role):
            target = None  # seul un administrateur actif peut recevoir des projets d'autrui
        if target is None or target.pk == user.pk:
            raise TransferImpossible(
                "Aucun autre administrateur actif ne peut recevoir les projets et glossaires de traduction de ce "
                "compte. Créez ou réactivez d'abord un compte administrateur.")
        label = (user.display_name or user.get_full_name() or user.username)[:150]
        now = timezone.now()
        TranslationProject.objects.filter(owner=user).update(owner=target, transferred_from=label, transferred_at=now)
        Glossary.objects.filter(owner=user).update(owner=target, transferred_from=label, transferred_at=now)
    EngineSetting.objects.filter(user=user).delete()
    TranslationPreference.objects.filter(user=user).delete()
    return target, projects, glossaries


def on_user_pre_delete(sender, instance, **kwargs):
    """Suppression réelle d'un compte : même règle que l'anonymisation."""
    release_user_translation_data(instance)
