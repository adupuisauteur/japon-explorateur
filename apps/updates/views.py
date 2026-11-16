import hashlib
import mimetypes

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Catalogue, StoredFile
from apps.core.audit import log_action
from apps.core.redirects import safe_next
from apps.core.permissions import admin_required

from . import importers, services
from .models import ImportJob, IncomingRecord, SyncJob


@admin_required
def dashboard(request):
    catalogues = Catalogue.objects.exclude(code="local").annotate(
        n_records=Count("records", filter=~Q(records__record_status="deleted")))
    rows = []
    for c in catalogues:
        last = c.sync_jobs.exclude(kind="test").first()
        rows.append({"c": c, "last": last, "due": c.next_sync_due()})
    return render(request, "updates/dashboard.html", {
        "rows": rows,
        "syncs": SyncJob.objects.select_related("catalogue")[:15],
        "imports": ImportJob.objects.select_related("catalogue")[:15],
        "reviews": list(SyncJob.objects.filter(status="review")) + list(ImportJob.objects.filter(status="review")),
    })


@admin_required
@require_POST
def sync_launch(request, code):
    from .tasks import run_sync_job

    catalogue = get_object_or_404(Catalogue, code=code)
    if not catalogue.can_refresh:
        messages.warning(request, f"« {catalogue.name} » sert aux recherches et ne propose pas d'actualisation. "
                                  "Les notices déjà intégrées sont comparées à chaque nouvelle recherche.")
        return redirect(catalogue.get_absolute_url())
    kind = request.POST.get("kind", "incremental")
    if kind not in dict(SyncJob.KINDS):
        kind = "incremental"
    job = SyncJob.objects.create(catalogue=catalogue, kind=kind, triggered_by=request.user)
    log_action(request, "sync.launch", catalogue, f"{job.get_kind_display()} lancée")
    run_sync_job.delay(job.pk)
    job.refresh_from_db()
    messages.info(request, f"{job.get_kind_display()} de « {catalogue.name} » : {job.get_status_display().lower()}.")
    return redirect(job.get_absolute_url())


@admin_required
@require_POST
def sync_all(request):
    from .tasks import run_sync_job

    n = 0
    for c in Catalogue.objects.exclude(connector="").exclude(code="local").exclude(status__in=["disabled", "to_study",
                                                                                                "not_configured"]):
        if c.sync_paused or not c.can_refresh:
            continue
        job = SyncJob.objects.create(catalogue=c, kind="incremental", triggered_by=request.user)
        run_sync_job.delay(job.pk)
        n += 1
    messages.info(request, f"{n} actualisation(s) lancée(s). Les rapports apparaissent ci-dessous.")
    return redirect("updates:dashboard")


@admin_required
@require_POST
def toggle_pause(request, code):
    c = get_object_or_404(Catalogue, code=code)
    c.sync_paused = not c.sync_paused
    c.save(update_fields=["sync_paused"])
    messages.info(request, f"Actualisation {'suspendue' if c.sync_paused else 'reprise'} pour {c.name}.")
    return redirect("updates:dashboard")


def _incoming_page(request, qs):
    p = request.GET
    if p.get("comparison"):
        qs = qs.filter(comparison=p["comparison"])
    if p.get("decision"):
        qs = qs.filter(decision=p["decision"])
    if p.get("q"):
        qs = qs.filter(Q(data__original_title__icontains=p["q"]) | Q(source_id__icontains=p["q"]))
    return Paginator(qs.select_related("matched_record"), 50).get_page(p.get("page"))


@admin_required
def sync_detail(request, pk):
    job = get_object_or_404(SyncJob.objects.select_related("catalogue"), pk=pk)
    return render(request, "updates/sync_detail.html", {
        "job": job, "page": _incoming_page(request, job.incoming.all()),
        "summary": job.incoming.values("comparison", "decision").annotate(n=Count("pk")),
    })


@admin_required
@require_POST
def incoming_decide(request):
    """Validation globale, sélective ou mise en attente (§9.5)."""
    decision = request.POST.get("decision")
    if decision not in ("accept", "reject", "hold", "pending"):
        return redirect(safe_next(request, "/"))
    if request.POST.get("scope") == "all":
        filters = {"import_job_id": request.POST.get("import_job")} if request.POST.get("import_job") else {
            "sync_job_id": request.POST.get("sync_job")}
        qs = IncomingRecord.objects.filter(**filters).exclude(decision="applied").exclude(comparison="error")
        if request.POST.get("comparison"):
            qs = qs.filter(comparison=request.POST["comparison"])
    else:
        qs = IncomingRecord.objects.filter(pk__in=request.POST.getlist("ids")).exclude(decision="applied")
    n = qs.update(decision=decision)
    messages.info(request, f"{n} élément(s) : {dict(IncomingRecord.DECISIONS)[decision].lower()}.")
    return redirect(safe_next(request, "/"))


@admin_required
@require_POST
def sync_apply(request, pk):
    job = get_object_or_404(SyncJob, pk=pk)
    accepted = job.incoming.filter(decision="accept").count()
    if accepted > services.APPLY_INLINE_MAX:  # 2.0.0 (lot 10) : trop long pour une page (délai de 180 s)
        from .tasks import apply_sync_job

        job.status = "running"
        job.message = f"Intégration de {accepted} notice(s) en cours (tâche de fond)."
        job.save(update_fields=["status", "message"])
        log_action(request, "sync.apply", job.catalogue, "Intégration lancée en tâche de fond", accepted=accepted)
        apply_sync_job.delay(job.pk, request.user.pk)
        messages.info(request, f"Intégration de {accepted} notice(s) lancée en tâche de fond : rechargez la page "
                               "pour suivre l'avancement. Une interruption n'efface rien ; relancez pour continuer.")
        return redirect(job.get_absolute_url())
    stats = services.apply_sync(job, request.user)
    log_action(request, "sync.apply", job.catalogue, "Synchronisation intégrée", **stats)
    messages.success(request, f"Intégration : {stats['created']} créée(s), {stats['updated']} mise(s) à jour (historisées), "
                              f"{stats['marked_unavailable']} marquée(s) indisponible(s), {stats['errors']} erreur(s).")
    return redirect(job.get_absolute_url())


# --------------------------------------------------------------------------- imports


@admin_required
def import_new(request):
    catalogues = Catalogue.objects.exclude(code="local")
    if request.method == "POST":
        upload = request.FILES.get("file")
        catalogue = Catalogue.objects.filter(code=request.POST.get("catalogue")).first()
        if not upload or not catalogue:
            messages.error(request, "Choisissez un fichier et une source.")
            return redirect("updates:import_new")
        try:
            services.validate_upload(upload)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("updates:import_new")
        h = hashlib.sha256()
        for chunk in upload.chunks():
            h.update(chunk)
        upload.seek(0)
        stored = StoredFile.objects.create(kind="import", file=upload,
                                           original_name=importers.safe_filename(upload.name),
                                           mime_type=mimetypes.guess_type(upload.name)[0] or "", size=upload.size,
                                           sha256=h.hexdigest(), uploaded_by=request.user,
                                           rights=request.POST.get("rights", ""))
        previous = ImportJob.objects.filter(file_sha256=h.hexdigest()).exclude(status="cancelled").first()
        job = ImportJob.objects.create(catalogue=catalogue, file=stored, file_name=upload.name, file_sha256=h.hexdigest(),
                                       created_by=request.user, dataset_label=request.POST.get("dataset_label", "")[:200],
                                       archive_source=bool(request.POST.get("archive_source")),
                                       preset=request.POST.get("preset", "auto"),
                                       format=request.POST.get("format", "") or (
                                           request.POST.get("preset") if request.POST.get("preset") in
                                           ("json_export", "marcxml", "dc") else ""))
        if previous:
            messages.warning(request, f"Ce fichier a déjà été importé (import n°{previous.pk}). Les notices existantes ne "
                                      "seront pas dupliquées.")
        try:
            services.analyze_import(job)
        except Exception as exc:
            from apps.incidents.services import record_exception

            job.status = "failed"
            job.errors = [{"row": None, "error": f"Lecture impossible : {exc}"}]
            job.save()
            record_exception(exc, module="importation", operation=f"Lecture du fichier d'import n°{job.pk}",
                             source_code=job.catalogue.code if job.catalogue_id else "", category="erreur_traitement",
                             severity="warning", origin="traitement",
                             extra={"format": job.format, "preset": job.preset, "taille_octets": upload.size})
            messages.error(request, f"Le fichier n'a pas pu être lu : {exc}")
        log_action(request, "import.upload", job, upload.name)
        return redirect(job.get_absolute_url())
    return render(request, "updates/import_new.html", {
        "catalogues": catalogues, "presets": importers.PRESETS, "formats": ImportJob.FORMATS,
        "selected": request.GET.get("catalogue", ""),
    })


@admin_required
def import_detail(request, pk):
    job = get_object_or_404(ImportJob.objects.select_related("catalogue", "file"), pk=pk)
    if request.method == "POST" and job.status in ("pending", "review", "failed"):
        action = request.POST.get("action")
        if action in ("save_mapping", "stage"):
            mapping = {}
            for field in importers.FIELD_LABELS:
                cols = [c for c in request.POST.getlist(f"map_{field}") if c in job.columns]
                if cols:
                    mapping[field] = cols if len(cols) > 1 else cols[0]
            job.mapping = mapping
            job.unknown_columns = importers.unknown_columns(job.columns, mapping)
            job.duplicate_strategy = request.POST.get("duplicate_strategy", job.duplicate_strategy)
            job.dataset_label = request.POST.get("dataset_label", job.dataset_label)[:200]
            if request.POST.get("sheet_name") and request.POST["sheet_name"] != job.sheet_name:
                job.sheet_name = request.POST["sheet_name"]
                job.mapping = {}
                job.save()
                services.analyze_import(job)
                messages.info(request, "Feuille changée : correspondance recalculée.")
                return redirect(job.get_absolute_url())
            job.save()
            if action == "stage":
                if "source_id" not in mapping and not request.POST.get("generate_ids"):
                    messages.error(request, "Indiquez la colonne d'identifiant source, ou cochez la génération "
                                            "d'identifiants à partir du contenu.")
                    return redirect(job.get_absolute_url())
                if "original_title" not in mapping:
                    messages.error(request, "Indiquez la colonne du titre.")
                    return redirect(job.get_absolute_url())
                from .tasks import stage_import_job

                stage_import_job.delay(job.pk, bool(request.POST.get("generate_ids")))
                messages.info(request, "Comparaison avec la base effectuée : vérifiez le rapport avant intégration.")
            else:
                messages.success(request, "Correspondance enregistrée.")
        elif action == "apply" and job.status == "review":
            stats = services.apply_import(job, request.user)
            log_action(request, "import.apply", job, job.file_name, **stats)
            messages.success(request, f"Import intégré : {stats['created']} notice(s) créée(s), {stats['updated']} mise(s) à "
                                      f"jour avec historique, {stats['errors']} erreur(s).")
        elif action == "cancel":
            job.status = "cancelled"
            job.save(update_fields=["status"])
            messages.info(request, "Import annulé : aucune notice n'a été modifiée.")
        return redirect(job.get_absolute_url())
    job.refresh_from_db()
    sample_rows = [[row.get(c, "") for c in job.columns] for row in job.sample]
    mapping_rows = []
    for field, label in importers.FIELD_LABELS.items():
        current = job.mapping.get(field, [])
        mapping_rows.append((field, label, current if isinstance(current, list) else [current]))
    preview = [importers.build_data(row, job.mapping) for row in job.sample[:3]]
    return render(request, "updates/import_detail.html", {
        "job": job, "sample_rows": sample_rows, "mapping_rows": mapping_rows, "preview": preview,
        "page": _incoming_page(request, job.incoming.all()) if job.status != "pending" else None,
        "summary": job.incoming.values("comparison", "decision").annotate(n=Count("pk")),
        "strategies": ImportJob.DUPLICATE_STRATEGIES,
    })
