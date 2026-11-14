"""
Droits d'accès du module de traduction (décisions C2, D3, D4 du 13 novembre 2026).

- Module réservé aux rôles Administrateur et Chercheur (le Lecteur n'y a pas accès), comme le module IA.
- Un projet appartient à un seul utilisateur (pas de partage en 1.3.0).
- L'administrateur voit et modifie les projets NON confidentiels des autres, selon la convention de
  l'application (dossiers, exports). Pour un projet confidentiel d'un autre compte, il ne voit que les
  métadonnées : titre, propriétaire, taille.
- Seul le propriétaire valide les traductions d'un projet.
"""
from django.core.exceptions import PermissionDenied
from django.db.models import Q


def can_use_translation(user):
    return bool(user and user.is_authenticated and user.can_edit)


def _is_owner(user, project):
    return project.owner_id == user.pk


def can_view_project(user, project):
    """Accès au CONTENU (documents, segments, traductions, exports)."""
    if not can_use_translation(user):
        return False
    return _is_owner(user, project) or (user.is_admin_role and not project.confidential)


def can_view_project_metadata(user, project):
    if not can_use_translation(user):
        return False
    return _is_owner(user, project) or user.is_admin_role


def can_edit_project(user, project):
    return can_view_project(user, project)


def can_validate_project(user, project):
    return can_use_translation(user) and _is_owner(user, project)


def projects_with_content_for(user):
    """Projets dont l'utilisateur peut voir le contenu."""
    from .models import TranslationProject

    if not can_use_translation(user):
        return TranslationProject.objects.none()
    if user.is_admin_role:
        return TranslationProject.objects.filter(Q(owner=user) | Q(confidential=False))
    return TranslationProject.objects.filter(owner=user)


def projects_metadata_only_for(user):
    """Projets confidentiels d'autres comptes, visibles par l'administrateur en métadonnées seulement."""
    from .models import TranslationProject

    if not (can_use_translation(user) and user.is_admin_role):
        return TranslationProject.objects.none()
    return TranslationProject.objects.filter(confidential=True).exclude(owner=user)


def can_view_glossary(user, glossary):
    """Propriétaire ; administrateur aussi, sauf si le glossaire sert un projet confidentiel (décision D3)."""
    if not can_use_translation(user):
        return False
    if glossary.owner_id == user.pk:
        return True
    return user.is_admin_role and not glossary.projects.filter(confidential=True).exists()


def glossaries_visible_for(user):
    from .models import Glossary

    if not can_use_translation(user):
        return Glossary.objects.none()
    if user.is_admin_role:
        return Glossary.objects.exclude(pk__in=glossaries_metadata_only_for(user).values("pk"))
    return Glossary.objects.filter(owner=user)


def glossaries_metadata_only_for(user):
    from .models import Glossary

    if not (can_use_translation(user) and user.is_admin_role):
        return Glossary.objects.none()
    return Glossary.objects.exclude(owner=user).filter(projects__confidential=True).distinct()


def can_edit_glossary(user, glossary):
    return can_view_glossary(user, glossary)


def require(condition):
    if not condition:
        raise PermissionDenied("Votre rôle ou ce projet ne permet pas cette action.")
