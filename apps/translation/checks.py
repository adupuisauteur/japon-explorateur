"""
Contrôles à la réception d'une traduction (cahier des charges § 8.3).

Ils signalent, sans bloquer l'enregistrement : traduction vide, identique à l'original, ou contenant
encore une forte proportion de japonais (signe fréquent d'une langue non reconnue). Les noms propres
laissés en kanji sont fréquents : le seuil est volontairement élevé et réglable.
Le contrôle terminologique (glossaires) s'ajoute au lot 7.
"""
from django.conf import settings

from .memory import normalize


def japanese_share(text):
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    jp = sum(1 for ch in chars if 0x3040 <= ord(ch) <= 0x30FF or 0x3400 <= ord(ch) <= 0x9FFF or 0xF900 <= ord(ch) <= 0xFAFF)
    return jp / len(chars)


def check_translation(source, text, *, simulated=False, target="fr"):
    """Retourne la liste des alertes (chaînes lisibles)."""
    if simulated:
        return ["Simulation : aucune traduction réelle"]
    alerts = []
    if not (text or "").strip():
        return ["traduction vide"]
    if normalize(text) == normalize(source) and japanese_share(source) > 0:
        alerts.append("traduction identique à l'original")
    elif target != "ja" and japanese_share(text) > settings.TRANSLATION_JAPANESE_ALERT_SHARE:
        alerts.append(f"la traduction contient encore {japanese_share(text):.0%} de caractères japonais")
    return alerts
