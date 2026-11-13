"""Préférences IA par utilisateur. Valeurs initiales conformes au §11.2 (AT-IA-01)."""
from .models import AIPreferenceProfile

INITIAL_PREFERENCES = {
    "mode": "demand",
    "translation_enabled": True,
    "summary_enabled": True,
    "classification_enabled": False,
    "duplicates_enabled": True,
    "store_inputs": False,
}


def create_initial_profile(user):
    return AIPreferenceProfile.objects.create(user=user, name="Profil par défaut", is_active=True,
                                              **INITIAL_PREFERENCES)


def active_profile(user):
    profile = AIPreferenceProfile.objects.filter(user=user, is_active=True).first()
    if profile is None:
        profile = AIPreferenceProfile.objects.filter(user=user).first()
        if profile is None:
            return create_initial_profile(user)
        profile.is_active = True
        profile.save(update_fields=["is_active"])
    return profile


def activate_profile(user, profile):
    """Changer de profil ne déclenche jamais de traitement (AT-IA-05)."""
    AIPreferenceProfile.objects.filter(user=user).update(is_active=False)
    profile.is_active = True
    profile.save(update_fields=["is_active"])
    return profile
