"""
Consommation du module de traduction (plan 1.3.0, lot 10 ; cahier des charges § 14).

Par moteur et par mois : caractères envoyés, nombre de traductions reçues, coût estimé. Les chiffres sont
la SOMME DES TÂCHES du mois (une tâche compte pour le mois de sa création, comme pour les plafonds) :
- caractères : TranslationJob.chars_sent (zéro pour une traduction simulée ou reprise de la mémoire) ;
- traductions : éléments traduits (versions de segments ou propositions de notices) ;
- coût : somme des coûts enregistrés avec chaque traduction (part du coût de l'appel), par devise ;
  pour les IA, il s'agit du coût des tâches IA (décision E1), calculé avec les tarifs du module IA.
Les traductions faites par l'ancienne fonction de traduction du module IA (avant la 1.3.0) sont reprises
sur une ligne à part, depuis les tâches IA.
Tous les montants sont des ESTIMATIONS : la facture du fournisseur fait foi.
"""
from collections import OrderedDict
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.ai.models import PROVIDERS as AI_PROVIDERS

from .models import ENGINES, EngineSetting, TranslationJob
from .services import SPENDING_STATUSES, monthly_chars

MONTHS_SHOWN = 12


def month_bounds(year, month):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(timezone.datetime(year, month, 1), tz)
    end = timezone.make_aware(timezone.datetime(year + (month == 12), month % 12 + 1, 1), tz)
    return start, end


def recent_months(today=None):
    today = today or timezone.localdate()
    out, y, m = [], today.year, today.month
    for _ in range(MONTHS_SHOWN):
        out.append(date(y, m, 1))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def parse_month(value):
    try:
        y, m = (int(x) for x in (value or "").split("-"))
        if 2000 <= y <= 2100 and 1 <= m <= 12:
            return date(y, m, 1)
    except ValueError:
        pass
    return timezone.localdate().replace(day=1)


def engine_key(job):
    if job.engine == "ai":
        provider = dict(AI_PROVIDERS).get(job.ai_provider, job.ai_provider)
        return f"ai:{job.ai_provider}:{job.ai_model}", f"{provider} — {job.ai_model}", "ai"
    return job.engine, dict(ENGINES).get(job.engine, job.engine), job.engine


def job_cost(job):
    """{devise: montant} : somme des coûts enregistrés avec les traductions de la tâche."""
    costs = {}
    for item in job.items.filter(status="done").select_related("version", "editorial"):
        amount, currency = None, ""
        if item.version_id:
            amount, currency = item.version.cost_estimate, item.version.currency
        elif item.editorial_id:
            data = item.editorial.data or {}
            if data.get("cost_estimate") not in (None, ""):
                amount, currency = Decimal(str(data["cost_estimate"])), data.get("currency", "")
        if amount is not None:
            costs[currency or "?"] = costs.get(currency or "?", Decimal("0")) + amount
    return costs


def _add(target, costs):
    for currency, amount in costs.items():
        target[currency] = target.get(currency, Decimal("0")) + amount


def monthly_usage(user, month):
    """Lignes par moteur pour le mois `month` (date du 1er), totaux par devise, détail des tâches."""
    start, end = month_bounds(month.year, month.month)
    jobs = (TranslationJob.objects.filter(user=user, status__in=SPENDING_STATUSES, created_at__gte=start,
                                          created_at__lt=end)
            .exclude(kind="package").select_related("project").order_by("created_at"))
    rows, detail, totals = OrderedDict(), [], {}
    for job in jobs:
        key, label, code = engine_key(job)
        row = rows.setdefault(key, {"label": label, "code": code, "jobs": 0, "chars": 0, "translations": 0,
                                    "simulated": 0, "costs": {}, "tokens_in": 0, "tokens_out": 0})
        costs = job_cost(job)
        done = job.items.filter(status="done").count()
        simulated = job.items.filter(status="done", version__simulated=True).count()
        row["jobs"] += 1
        row["chars"] += job.chars_sent
        row["translations"] += done
        row["simulated"] += simulated
        _add(row["costs"], costs)
        _add(totals, costs)
        if code == "ai":
            from apps.ai.models import AITask

            agg = AITask.objects.filter(translation_job_items__job=job).distinct().aggregate(
                i=Sum("tokens_in"), o=Sum("tokens_out"))
            row["tokens_in"] += agg["i"] or 0
            row["tokens_out"] += agg["o"] or 0
        detail.append({"job": job, "label": label, "costs": costs, "done": done})
    legacy = _legacy_ai(user, start, end)
    if legacy["tasks"]:
        _add(totals, legacy["costs"])
    return {"rows": list(rows.values()), "totals": totals, "detail": detail, "legacy": legacy,
            "chars": sum(r["chars"] for r in rows.values()),
            "translations": sum(r["translations"] for r in rows.values())}


def _legacy_ai(user, start, end):
    """Tâches IA de traduction hors module de traduction (ancienne fonction du module IA)."""
    from apps.ai.models import AITask

    qs = (AITask.objects.filter(user=user, function="translation", created_at__gte=start, created_at__lt=end)
          .filter(translation_job_items__isnull=True).exclude(parameters__has_key="translation_job"))
    costs = {}
    for task in qs:
        if task.cost_estimate is not None:
            _add(costs, {"USD": task.cost_estimate})
    agg = qs.aggregate(i=Sum("tokens_in"), o=Sum("tokens_out"))
    return {"tasks": qs.count(), "costs": costs, "tokens_in": agg["i"] or 0, "tokens_out": agg["o"] or 0}


def caps(user):
    """Plafonds du mois en cours : caractères par moteur (Traduction → Moteurs) et budget IA (préférences IA)."""
    out = []
    for setting in EngineSetting.objects.filter(user=user).exclude(monthly_char_cap=None).order_by("engine"):
        used = monthly_chars(user, setting.engine)
        out.append({"label": setting.get_engine_display(), "used": used, "cap": setting.monthly_char_cap,
                    "unit": "caractères", "share": min(100, int(used * 100 / setting.monthly_char_cap))
                    if setting.monthly_char_cap else 100})
    from apps.ai.preferences import active_profile
    from apps.ai.services import monthly_spend

    profile = active_profile(user)
    if profile.monthly_budget is not None:
        spent = monthly_spend(user)
        budget = profile.monthly_budget
        out.append({"label": "Intelligences artificielles (toutes fonctions IA)", "used": spent, "cap": budget,
                    "unit": "USD", "share": min(100, int(spent * 100 / budget)) if budget else 100})
    return out
