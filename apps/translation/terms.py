"""
Conditions d'utilisation des textes envoyés aux fournisseurs en ligne (cahier des charges § 13).

Avant le PREMIER envoi à chaque fournisseur en ligne, l'utilisateur voit le résumé daté de ses conditions
(conservation, utilisation pour l'amélioration du service, différences entre offre gratuite et payante)
avec le lien vers les conditions officielles, et confirme en avoir pris connaissance. Le résumé est tenu
dans reference/conditions-fournisseurs.json ; une nouvelle date de vérification d'un fournisseur demande
une nouvelle prise de connaissance.

La prise de connaissance est enregistrée dans le journal des actions (AuditLog, action
« translation.terms_acknowledged ») : pas de nouvelle table. Les moteurs locaux (Argos) n'envoient rien.
"""
import json
from functools import lru_cache
from pathlib import Path

TERMS_FILE = Path(__file__).resolve().parent / "reference" / "conditions-fournisseurs.json"
ACTION = "translation.terms_acknowledged"
ONLINE_ENGINES = {"deepl", "google_basic", "ai"}


@lru_cache(maxsize=1)
def _table():
    return json.loads(TERMS_FILE.read_text(encoding="utf-8"))


def provider_key(engine_code, ai_provider=""):
    if engine_code == "ai":
        # 2.0.0 (lot 4) : l'IA locale (Ollama) tourne sur l'ordinateur ; aucune condition de fournisseur à lire
        return f"ai:{ai_provider}" if ai_provider and ai_provider != "ollama" else ""
    return engine_code if engine_code in ONLINE_ENGINES else ""


def terms_for(key):
    entry = (_table().get("providers") or {}).get(key)
    if entry is None:
        return None
    return dict(entry, key=key)


def acknowledged(user, key):
    from apps.core.models import AuditLog

    entry = terms_for(key)
    if entry is None:
        return True
    return AuditLog.objects.filter(user=user, action=ACTION, details__provider=key,
                                   details__verified_on=entry["verified_on"]).exists()


def needed(user, engine_code, ai_provider=""):
    """Résumé à présenter avant l'envoi, ou None (moteur local, ou résumé déjà lu dans sa version actuelle)."""
    key = provider_key(engine_code, ai_provider)
    if not key:
        return None
    entry = terms_for(key)
    if entry is None:
        # Fournisseur sans résumé : on le signale plutôt que de l'ignorer.
        return {"key": key, "name": key, "verified_on": "", "sources": [],
                "points": ["Aucun résumé vérifié n'est disponible pour ce fournisseur : consultez ses conditions."]}
    return None if acknowledged(user, key) else entry


def acknowledge(user, key, request=None):
    from apps.core.audit import log_action

    entry = terms_for(key) or {"name": key, "verified_on": ""}
    if acknowledged(user, key) and terms_for(key) is not None:
        return
    log_action(request or user, ACTION, None, f"Conditions de {entry['name']} lues (vérifiées le {entry['verified_on']})",
               provider=key, verified_on=entry["verified_on"])


def all_terms():
    return [dict(v, key=k) for k, v in (_table().get("providers") or {}).items()]
