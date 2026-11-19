from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from apps.core.permissions import admin_required

from . import pages as P


def _page_or_404(request, slug):
    page = P.fresh_registry().pages.get(slug)
    if page is None or not page.visible_to(request.user):
        raise Http404("Page d'aide introuvable.")
    return page


@login_required
def index(request):
    groups = {}
    for page in P.visible_pages(request.user):
        groups.setdefault(page.section, []).append(page)
    return render(request, "help/index.html", {"groups": list(groups.items()), "query": ""})


@login_required
def page(request, slug):
    current = _page_or_404(request, slug)
    siblings = [p for p in P.visible_pages(request.user) if p.section == current.section]
    return render(request, "help/page.html", {"page": current, "html": mark_safe(current.html),  # noqa: S308
                                              "siblings": siblings})


@login_required
def search(request):
    query = request.GET.get("q", "").strip()[:100]
    return render(request, "help/search.html", {"query": query, "hits": P.search(request.user, query) if query else []})


@admin_required
def history(request):
    """Administration → Historique des versions (U4) : évolutions et améliorations, version par version."""
    current = P.fresh_registry().pages.get("historique-des-versions")
    if current is None:
        raise Http404("Historique absent.")
    return render(request, "help/history.html", {"page": current, "html": mark_safe(current.html)})  # noqa: S308
