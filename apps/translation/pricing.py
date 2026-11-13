"""
Estimation du coût avant envoi (décision C4). Les montants sont des ESTIMATIONS : la facture du
fournisseur fait foi.

- DeepL, Google, Argos : tarif par million de caractères, lu dans reference/tarifs-traduction.json
  (daté, devise d'origine, sans conversion). Tarif absent (null) = estimation non disponible.
- IA : tarifs saisis dans le module IA (AIModelPrice, USD). Le nombre de jetons est inconnu avant
  l'envoi : il est approché à partir du nombre de caractères (approximation affichée comme telle).
"""
import json
from decimal import Decimal
from pathlib import Path

PRICES_FILE = Path(__file__).resolve().parent / "reference" / "tarifs-traduction.json"

#: approximation des jetons pour l'estimation IA (japonais ≈ 1 jeton par caractère ; traduction plus longue)
TOKENS_PER_SOURCE_CHAR = Decimal("1.2")
TOKENS_OUT_PER_SOURCE_CHAR = Decimal("1.6")
PROMPT_TOKENS_PER_BATCH = 450


def price_table():
    return json.loads(PRICES_FILE.read_text(encoding="utf-8"))


def estimate(engine, chars, *, ai_provider="", ai_model="", batches=1):
    """Retourne {"amount": Decimal|None, "currency": str, "basis": str, "tokens_in": int, "tokens_out": int}."""
    if engine == "ai":
        from apps.ai.models import AIModelPrice

        tokens_in = int(Decimal(chars) * TOKENS_PER_SOURCE_CHAR) + PROMPT_TOKENS_PER_BATCH * max(batches, 1)
        tokens_out = int(Decimal(chars) * TOKENS_OUT_PER_SOURCE_CHAR)
        amount = AIModelPrice.estimate(ai_provider, ai_model, tokens_in, tokens_out)
        basis = ("tarif du module IA ; nombre de jetons approché à partir des caractères" if amount is not None
                 else "aucun tarif saisi pour ce modèle (IA → Tarifs)")
        return {"amount": amount, "currency": "USD" if amount is not None else "", "basis": basis,
                "tokens_in": tokens_in, "tokens_out": tokens_out}
    table = price_table()
    entry = (table.get("engines") or {}).get(engine) or {}
    rate = entry.get("per_million_chars")
    if rate is None:
        return {"amount": None, "currency": "", "basis": "tarif non renseigné (reference/tarifs-traduction.json)",
                "tokens_in": 0, "tokens_out": 0}
    amount = Decimal(str(rate)) * Decimal(chars) / Decimal(1_000_000)
    return {"amount": amount, "currency": entry.get("currency", ""),
            "basis": f"tarif du {table.get('date', '?')}" + (f", vérifié le {entry['verified_on']}"
                                                            if entry.get("verified_on") else ""),
            "tokens_in": 0, "tokens_out": 0}
