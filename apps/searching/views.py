from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import DOCUMENT_TYPES, PERIODS, Catalogue
from apps.catalog.search import suggest_variants
from apps.core import japanese as jp
from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from . import services
from .forms import SearchForm
from .models import EXCLUSION_REASONS, SavedSearch, SearchResult, SearchSession


def _default_sources(user):
    searchable = [c.code for c in Catalogue.objects.all() if c.is_searchable]
    preferred = [c for c in (user.preferred_sources or []) if c in searchable]
    return preferred or searchable


def _get_session(request, uid):
    session = get_object_or_404(SearchSession, uid=uid)
    if session.owner_id != request.user.pk and not request.user.is_admin_role:
        raise PermissionDenied
    return session


@login_required
def search_form(request):
    initial = {"sources": _default_sources(request.user), "mode": request.user.effective_search_mode(),
               "q": request.GET.get("q", ""), "date_kind": "any"}
    if request.GET.get("from_session"):
        prev = _get_session(request, request.GET["from_session"])
        initial.update({"q": prev.query, "sources": prev.sources, "mode": prev.mode, **(prev.fields or {}),
                        **{k: v for k, v in (prev.filters or {}).items() if k != "catalogues"}})
    form = SearchForm(initial=initial, user=request.user)
    return render(request, "searching/form.html", {"form": form, "ai_variants": request.session.pop("ai_variants", None),
                                                   "unverified": _unverified_codes()})


def _unverified_codes():
    return [c.code for c in Catalogue.objects.exclude(connector="") if c.needs_real_verification]


@login_required
def variants(request):
    q = request.GET.get("q", "").strip()
    return render(request, "searching/_variants.html", {"suggestions": suggest_variants(q), "q": q})


@login_required
def quick(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return redirect("searching:form")
    session = services.create_session(request.user, query=q, sources=_default_sources(request.user))
    return redirect(session.get_absolute_url())


@login_required
@require_POST
def launch(request):
    chosen_variants = request.POST.getlist("variants")
    # Variantes saisies librement (1.2.0) : graphies anciennes ou attestées que les règles ne devinent pas.
    import re as _re

    for v in _re.split(r"[;；、\n]+", request.POST.get("custom_variants", ""))[:10]:
        v = v.strip()[:100]
        if v and v not in chosen_variants:
            chosen_variants.append(v)
    form = SearchForm(request.POST, user=request.user, extra_variants=chosen_variants)
    if not form.is_valid():
        return render(request, "searching/form.html", {"form": form, "unverified": _unverified_codes()}, status=400)
    d = form.cleaned_data
    if request.user.role == "reader" and d["mode"] == "auto":
        d["mode"] = "manual"
    if d.get("remember_sources"):
        request.user.preferred_sources = d["sources"]
        request.user.save(update_fields=["preferred_sources"])
    details = [s for s in suggest_variants(d["q"]) if s["value"] in chosen_variants]
    details += [{"value": v, "kind": "Saisie ou proposition validée", "origin": "utilisateur", "verification": "validée"}
                for v in chosen_variants if v not in {x["value"] for x in details}]
    collection = None
    if d.get("target_collection"):
        from apps.library.models import Collection

        collection = Collection.objects.filter(pk=d["target_collection"], owner=request.user).first()
    session = services.create_session(
        request.user, query=d["q"], variants=chosen_variants, variant_details=details,
        fields={k: d[k] for k in ("title", "creator", "subject", "place", "date_from", "date_to") if d.get(k)},
        filters={k: d[k] for k in ("period", "document_type", "material_type", "digital_access", "language", "date_kind")
                 if d.get(k)},
        sources=d["sources"], mode=d["mode"], target_collection=collection,
    )
    return redirect(session.get_absolute_url())


@login_required
def session_detail(request, uid):
    session = _get_session(request, uid)
    catalogues = {c.code: c for c in Catalogue.objects.filter(code__in=session.sources)}
    sources = [(code, catalogues.get(code), session.source_stats.get(code, {})) for code in session.sources]
    return render(request, "searching/session.html", {
        "session": session, "sources": sources, "counts": session.counts(),
        "reasons": EXCLUSION_REASONS, "periods": [p for p in PERIODS if p[0]],
        "doc_types": [d for d in DOCUMENT_TYPES if d[0]],
        "comparison_counts": {c: session.results.filter(comparison=c).count()
                              for c in ("new", "known", "modified", "unavailable", "not_comparable")}
        if session.previous_session_id else None,
    })


@login_required
@require_POST
def run_source(request, uid, code):
    session = _get_session(request, uid)
    if code not in session.sources:
        raise PermissionDenied
    stats = session.source_stats.get(code, {})
    if stats.get("status") in ("pending", None) or request.POST.get("retry"):
        stats = services.run_source(session, code)
    catalogue = Catalogue.objects.filter(code=code).first()
    response = render(request, "searching/_source_status.html",
                      {"session": session, "code": code, "catalogue": catalogue, "stats": stats})
    response["HX-Trigger"] = "results-changed"
    return response


def _filtered_results(session, params):
    qs = session.results.select_related("catalogue", "local_record")
    if params.get("source"):
        qs = qs.filter(catalogue__code=params["source"])
    if params.get("decision"):
        qs = qs.filter(decision=params["decision"])
    if params.get("comparison"):
        qs = qs.filter(comparison=params["comparison"])
    if params.get("period"):
        qs = qs.filter(data__norm__period=params["period"])
    if params.get("doc_type"):
        qs = qs.filter(data__norm__document_type=params["doc_type"])
    if params.get("in_library") == "1":
        qs = qs.filter(in_library=True)
    elif params.get("in_library") == "0":
        qs = qs.filter(in_library=False)
    if params.get("within"):
        needle = params["within"]
        qs = qs.filter(Q(data__original_title__icontains=needle) | Q(data__creator_original__icontains=needle)
                       | Q(data__reading__icontains=needle))
    sort = params.get("sort") or "relevance"
    if params.get("digital") == "1":
        qs = qs.filter(data__norm__digital_access__in=["image", "fulltext"])
    order = {"title": ["data__original_title"], "source": ["catalogue__name", "rank"],
             "author": ["data__creator_original", "rank"],
             "institution": ["data__holding_institution_text", "catalogue__name", "rank"],
             "date": ["data__norm__composition_year_start", "data__norm__copy_year_start", "rank"],
             "collected": ["-collected_at"]}.get(sort, ["rank"])
    return qs.order_by(*order)


@login_required
def results(request, uid):
    session = _get_session(request, uid)
    params = request.GET
    page = Paginator(_filtered_results(session, params), 40).get_page(params.get("page"))
    return render(request, "searching/_results.html", {"session": session, "page": page,
                                                        "reasons": EXCLUSION_REASONS, "counts": session.counts()})


@login_required
def result_panel(request, uid, pk):
    session = _get_session(request, uid)
    result = get_object_or_404(SearchResult, session=session, pk=pk)
    return render(request, "searching/_result_panel.html", {"session": session, "r": result,
                                                            "log": result.decision_log.select_related("user")})


@login_required
@require_POST
def decide(request, uid):
    session = _get_session(request, uid)
    action = request.POST.get("action")
    ids = request.POST.getlist("result_ids")
    if request.POST.get("scope") == "all_visible":
        qs = _filtered_results(session, request.POST)
    else:
        qs = session.results.filter(pk__in=ids)
    if action == "select_all":
        qs, action = session.results.exclude(decision="excluded").exclude(comparison="unavailable"), "select"
    elif action == "deselect_all":
        qs, action = session.results.filter(decision="selected"), "deselect"
    try:
        n = services.set_decision(list(qs), action, request.user, reason=request.POST.get("reason", ""),
                                  note=request.POST.get("note", ""))
    except ValueError:
        return HttpResponse("Action inconnue.", status=400)
    if request.headers.get("HX-Request"):
        params = request.POST.copy()
        page = Paginator(_filtered_results(session, params), 40).get_page(params.get("page"))
        response = render(request, "searching/_results.html", {"session": session, "page": page,
                                                               "reasons": EXCLUSION_REASONS, "counts": session.counts()})
        response["HX-Trigger"] = "counts-changed"
        return response
    messages.info(request, f"{n} résultat(s) mis à jour.")
    return redirect(session.get_absolute_url())


@login_required
def counts(request, uid):
    session = _get_session(request, uid)
    return render(request, "searching/_counts.html", {"session": session, "counts": session.counts()})


@researcher_required
def integrate(request, uid):
    """Confirmation claire avant intégration en bibliothèque ou dans un dossier (§8.3)."""
    from apps.library.models import Collection

    session = _get_session(request, uid)
    selected = session.results.filter(decision="selected", integrated_record__isnull=True).select_related("catalogue")
    if request.method == "POST":
        collection = None
        to_collection = request.POST.get("dest", "collection") == "collection"
        if to_collection and request.POST.get("collection"):
            collection = get_object_or_404(Collection, pk=request.POST["collection"])
            if not collection.can_edit(request.user):
                raise PermissionDenied
        elif to_collection and request.POST.get("new_collection"):
            collection = Collection.objects.create(owner=request.user, title=request.POST["new_collection"][:300],
                                                   created_from_session=session,
                                                   description=f"Créé depuis la recherche « {session.query} »")
        stats = services.integrate(session, list(selected), request.user, collection=collection)
        log_action(request, "search.integrate", session, f"{stats['added_to_library']} ajout(s) en bibliothèque",
                   **{k: v for k, v in stats.items() if k != "errors"})
        msg = (f"Intégration terminée : {stats['created']} notice(s) créée(s), {stats.get('updated', 0)} mise(s) à jour "
               f"avec historique, {stats['added_to_library']} ajout(s) à votre bibliothèque")
        if collection:
            msg += f", {stats['added_to_collection']} ajout(s) au dossier « {collection.title} »"
        messages.success(request, msg + ".")
        for err in stats["errors"][:5]:
            messages.warning(request, err)
        return redirect(collection.get_absolute_url() if collection and request.POST.get("go_collection")
                        else session.get_absolute_url())
    return render(request, "searching/integrate.html", {
        "session": session, "selected": selected, "excluded_count": session.results.filter(decision="excluded").count(),
        "collections": Collection.objects.filter(owner=request.user),
        "already": session.results.filter(decision="selected", integrated_record__isnull=False).count(),
    })


@login_required
@require_POST
def save_search(request, uid):
    session = _get_session(request, uid)
    name = request.POST.get("name", "").strip() or session.query or "Recherche enregistrée"
    saved = SavedSearch.objects.create(owner=request.user, name=name[:200], params=session.search_params())
    session.saved_search = saved
    session.is_saved = True
    session.expires_at = None
    session.save(update_fields=["saved_search", "is_saved", "expires_at"])
    messages.success(request, f"Recherche « {saved.name} » enregistrée : vous pourrez la relancer et comparer les nouveautés.")
    return redirect(session.get_absolute_url())


@login_required
@require_POST
def keep_session(request, uid):
    session = _get_session(request, uid)
    session.is_saved = True
    session.expires_at = None
    session.save(update_fields=["is_saved", "expires_at"])
    messages.success(request, "Session conservée sans limite de durée.")
    return redirect(session.get_absolute_url())


@login_required
@require_POST
def delete_session(request, uid):
    session = _get_session(request, uid)
    session.delete()
    messages.info(request, "Session supprimée (les notices déjà intégrées sont conservées).")
    return redirect("searching:history")


@login_required
def history(request):
    qs = SearchSession.objects.filter(owner=request.user).select_related("saved_search")
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "searching/history.html", {"page": page})


@login_required
def saved_list(request):
    return render(request, "searching/saved_list.html",
                  {"saved": SavedSearch.objects.filter(owner=request.user)})


@login_required
def saved_detail(request, pk):
    saved = get_object_or_404(SavedSearch, pk=pk, owner=request.user)
    if request.method == "POST":
        saved.name = request.POST.get("name", saved.name)[:200]
        saved.notes = request.POST.get("notes", "")
        saved.save()
        messages.success(request, "Recherche mise à jour.")
    return render(request, "searching/saved_detail.html", {"saved": saved, "sessions": saved.sessions.all()})


@login_required
@require_POST
def saved_replay(request, pk):
    saved = get_object_or_404(SavedSearch, pk=pk, owner=request.user)
    session = services.replay(saved, request.user)
    messages.info(request, "Recherche relancée : les résultats sont comparés avec la dernière exécution, sans rien "
                           "écraser.")
    return redirect(session.get_absolute_url())


@login_required
@require_POST
def saved_delete(request, pk):
    saved = get_object_or_404(SavedSearch, pk=pk, owner=request.user)
    saved.delete()
    messages.info(request, "Recherche enregistrée supprimée.")
    return redirect("searching:saved_list")


@login_required
def romaji_preview(request):
    q = request.GET.get("q", "")
    return HttpResponse(jp.to_romaji(q) if jp.has_japanese(q) else "")
