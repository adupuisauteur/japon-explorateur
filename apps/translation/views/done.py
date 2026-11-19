"""2.0.0 (lot 3, demande U5) : « Traductions effectuées » — vue d'ensemble des notices et des documents traduits."""
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.shortcuts import render
from django.utils import timezone

from apps.catalog.models import EditorialContent
from apps.core.permissions import researcher_required

from ..models import ENGINES, TranslationDocument
from ..permissions import projects_with_content_for

STATES = [("", "Tous les états"), ("proposed", "Proposée"), ("validated", "Validée (adoptée dans la fiche)"),
          ("review", "À revoir : l'original a changé"), ("rejected", "Refusée")]
PERIODS = [("", "Toutes les dates"), ("7", "7 derniers jours"), ("30", "30 derniers jours"), ("365", "Douze mois")]


def _needs_review(ed):
    current = (getattr(ed.record, ed.target_field, "") or "").strip() if ed.target_field else ""
    return bool(ed.source_text and current and ed.source_text.strip() != current)


@researcher_required
def translations_done(request):
    state, engine, period = request.GET.get("etat", ""), request.GET.get("moteur", ""), request.GET.get("periode", "")
    q = request.GET.get("q", "").strip()
    qs = EditorialContent.objects.filter(kind="translation").select_related("record", "author")
    if state in ("proposed", "validated", "rejected"):
        qs = qs.filter(status=state)
    if engine in dict(ENGINES):
        qs = qs.filter(data__engine=engine)
    if period.isdigit():
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=int(period)))
    if q:
        qs = qs.filter(Q(record__original_title__icontains=q) | Q(content__icontains=q))
    rows = list(qs.order_by("-created_at")[:2000])
    from ..services import RECORD_FIELDS

    labels = dict(ENGINES)
    for ed in rows:
        ed.needs_review = _needs_review(ed)
        ed.engine_label = labels.get((ed.data or {}).get("engine", ""), (ed.data or {}).get("engine") or "—")
        ed.field_label = RECORD_FIELDS.get(ed.target_field, ed.target_field)
    if state == "review":
        rows = [ed for ed in rows if ed.needs_review and ed.status != "rejected"]
    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    documents = (TranslationDocument.objects.filter(project__in=projects_with_content_for(request.user))
                 .select_related("project")
                 .annotate(n_segments=Count("segments", distinct=True),
                           n_translated=Count("segments", filter=Q(segments__versions__isnull=False), distinct=True),
                           n_validated=Count("segments", filter=Q(segments__versions__status="validated"),
                                             distinct=True),
                           last=Max("segments__versions__created_at"))
                 .filter(n_translated__gt=0).order_by("-last")[:100])
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "translation/done.html", {
        "page": page, "documents": documents, "states": STATES, "engines": ENGINES, "periods": PERIODS,
        "state": state, "engine": engine, "period": period, "q": q, "query": params.urlencode(),
    })
