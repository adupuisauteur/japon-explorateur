"""Traduction → Consommation : caractères, traductions et coûts estimés par moteur et par mois (lot 10)."""
from django.shortcuts import render

from apps.core.permissions import researcher_required

from .. import usage as U


@researcher_required
def usage(request):
    month = U.parse_month(request.GET.get("mois"))
    return render(request, "translation/usage.html", {
        "month": month, "months": U.recent_months(), "data": U.monthly_usage(request.user, month),
        "caps": U.caps(request.user),
    })
