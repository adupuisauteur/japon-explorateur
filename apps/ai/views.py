from django import forms
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.catalog.models import Record
from apps.core.audit import log_action
from apps.core.redirects import safe_next, safe_url
from apps.core.forms import BootstrapMixin
from apps.core.permissions import admin_required, researcher_required

from . import services
from .crypto import encrypt_secret, encryption_available
from .models import FUNCTIONS, PROVIDERS, AIModelPrice, AIPreferenceProfile, AIProviderCredential, AITask
from .preferences import activate_profile, active_profile
from .providers import MAX_STORED_MODELS, ProviderError, get_provider, text_models
from .urlsafety import UnsafeProviderURL, allowed_local_urls, check_provider_url

OVERRIDABLE = ["translation", "summary", "classification", "duplicates", "query_extension", "extraction", "rag",
               "comparison"]


class ProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = AIPreferenceProfile
        fields = ["name", "mode", "translation_enabled", "summary_enabled", "classification_enabled",
                  "duplicates_enabled", "query_extension_enabled", "extraction_enabled", "rag_enabled",
                  "comparison_enabled", "default_provider", "default_model", "batch_extra_confirmation",
                  "store_inputs", "monthly_budget", "alert_threshold_pct"]
        widgets = {"mode": forms.RadioSelect}


@researcher_required
def preferences(request):
    profile = active_profile(request.user)
    if request.GET.get("profile"):
        profile = get_object_or_404(AIPreferenceProfile, pk=request.GET["profile"], user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        overrides = {}
        for fn in OVERRIDABLE:
            if fn == "translation" and f"ov_{fn}_provider" not in request.POST:
                # 1.3.0 : choix déplacé dans Traduction → Moteurs ; l'ancienne valeur est conservée telle quelle.
                previous = (profile.function_overrides or {}).get(fn)
                if previous:
                    overrides[fn] = previous
                continue
            prov = request.POST.get(f"ov_{fn}_provider", "")
            if prov in dict(PROVIDERS):
                overrides[fn] = {"provider": prov, "model": request.POST.get(f"ov_{fn}_model", "").strip()}
        obj.function_overrides = overrides
        obj.save()
        # Enregistrer des préférences ne déclenche aucun traitement (AT-IA-05, AT-IA-12).
        log_action(request, "ai.preferences", obj, f"Profil « {obj.name} » : mode {obj.get_mode_display()}")
        messages.success(request, "Préférences IA enregistrées. Aucun traitement n'a été lancé.")
        return redirect(f"{request.path}?profile={obj.pk}")
    credentials = {c.provider: c for c in AIProviderCredential.objects.filter(user=request.user)}
    return render(request, "ai/preferences.html", {
        "form": form, "profile": profile, "profiles": AIPreferenceProfile.objects.filter(user=request.user),
        # 1.3.0 : le moteur de traduction se choisit dans Traduction → Moteurs (ligne retirée de l'affichage).
        "functions": [(code, label) for code, label in FUNCTIONS if code in OVERRIDABLE and code != "translation"],
        "providers": PROVIDERS, "credentials": credentials,
        "spend": services.monthly_spend(request.user),
    })


@researcher_required
@require_POST
def profile_action(request, pk):
    profile = get_object_or_404(AIPreferenceProfile, pk=pk, user=request.user)
    action = request.POST.get("action")
    if action == "activate":
        activate_profile(request.user, profile)
        messages.success(request, f"Profil « {profile.name} » activé. Aucun traitement n'a été lancé.")
    elif action == "duplicate":
        profile.pk = None
        profile.is_active = False
        profile.name = f"{profile.name} (copie)"[:100]
        profile.save()
        messages.success(request, "Profil dupliqué.")
    elif action == "delete":
        if AIPreferenceProfile.objects.filter(user=request.user).count() <= 1:
            messages.error(request, "Gardez au moins un profil (vous pouvez le régler sur « Désactivée »).")
        else:
            was_active = profile.is_active
            profile.delete()
            if was_active:
                active_profile(request.user)
            messages.info(request, "Profil supprimé.")
    elif action == "disable_all":
        profile.mode = "disabled"
        profile.save(update_fields=["mode"])
        messages.info(request, "IA désactivée pour ce profil.")
    return redirect("ai:preferences")


@researcher_required
def providers(request):
    credentials = {c.provider: c for c in AIProviderCredential.objects.filter(user=request.user)}
    return render(request, "ai/providers.html", {
        # 2.0.0 (lot 4) : l'IA locale n'a pas de clé ; elle se gère dans Traduction → Moteurs locaux
        "rows": [(code, label, credentials.get(code)) for code, label in PROVIDERS if code != "ollama"],
        "encryption_ok": encryption_available(), "local_urls": sorted(allowed_local_urls()),
    })


@researcher_required
@require_POST
def provider_save(request, provider):
    if provider not in dict(PROVIDERS) or provider == "ollama":
        return redirect("ai:providers")
    cred, _ = AIProviderCredential.objects.get_or_create(user=request.user, provider=provider)
    action = request.POST.get("action", "save")
    if action == "revoke":
        cred.encrypted_key = ""
        cred.status = "revoked"
        cred.available_models = []
        cred.save()
        log_action(request, "ai.key_revoked", cred, cred.get_provider_display())
        messages.info(request, "Clé révoquée et effacée du serveur.")
        return redirect("ai:providers")
    if action == "test":
        try:
            models = text_models(provider, get_provider(cred).list_models())
            cred.status = "ok"
            cred.available_models = models[:MAX_STORED_MODELS]
            cred.last_error = ""
            messages.success(request, f"Connexion réussie : {len(models)} modèle(s) de texte disponible(s).")
        except (ProviderError, ImproperlyConfigured) as exc:
            cred.status = "error"
            cred.last_error = str(exc)[:500]
            messages.error(request, f"Échec du test : {exc}")
        cred.last_tested_at = timezone.now()
        cred.save()
        return redirect("ai:providers")
    key = request.POST.get("api_key", "").strip()
    if provider == "openai_compatible" and "base_url" in request.POST:
        # Adresse personnalisée : réservée à l'administrateur et contrôlée (anti-SSRF).
        if not request.user.is_admin_role:
            messages.error(request, "Seul un administrateur peut définir l'adresse d'un service compatible.")
            return redirect("ai:providers")
        try:
            cred.base_url = check_provider_url(request.POST.get("base_url", ""))
        except UnsafeProviderURL as exc:
            messages.error(request, f"Adresse refusée : {exc}")
            return redirect("ai:providers")
        log_action(request, "ai.base_url", cred, f"Adresse du service compatible : {cred.base_url}")
    if key:
        try:
            cred.encrypted_key = encrypt_secret(key)
        except ImproperlyConfigured as exc:
            messages.error(request, str(exc))
            return redirect("ai:providers")
        cred.status = "untested"
        cred.available_models = []
        log_action(request, "ai.key_saved", cred, f"Clé {cred.get_provider_display()} enregistrée (chiffrée)")
        messages.success(request, "Clé enregistrée et chiffrée. Elle ne sera plus jamais affichée. "
                                  "Testez la connexion ; aucun traitement n'est lancé.")
    cred.save()
    return redirect("ai:providers")


def _records_from_request(request):
    ids = []
    for v in request.POST.getlist("record_ids"):
        ids.extend(i for i in v.split(",") if i)
    return list(Record.objects.filter(record_id__in=ids).select_related("catalogue"))


@researcher_required
@require_POST
def launch(request):
    """Prépare une tâche (brouillon) puis affiche l'écran de confirmation. Aucun envoi à ce stade."""
    function = request.POST.get("function", "")
    records = _records_from_request(request)
    parameters = {}
    scope = f"{len(records)} notice(s)"
    if function == "query_extension":
        parameters["query"] = request.POST.get("q", "").strip()
        scope = f"requête « {parameters['query']} »"
        if not parameters["query"]:
            messages.error(request, "Saisissez d'abord une requête.")
            return redirect("searching:form")
    if function == "rag":
        parameters["question"] = request.POST.get("question", "").strip()
        records = services.rag_context(parameters["question"])
        scope = f"question + {len(records)} notice(s) du fonds local"
    if function == "duplicates" and request.POST.get("with_candidates") and len(records) == 1:
        from apps.catalog.services import duplicate_candidates

        records += [other for other, _, _ in duplicate_candidates(records[0], limit=15)]
        scope = f"1 notice + {len(records) - 1} candidate(s) proposées par les règles"
    provider = request.POST.get("provider") or None
    model = request.POST.get("model") or None
    try:
        task = services.prepare_task(request.user, function, records=records, parameters=parameters,
                                     provider=provider, model=model, scope_label=scope)
    except services.AIUnavailable as exc:
        return render(request, "ai/unavailable.html", {
            "error": str(exc), "reason": exc.reason, "alternatives": exc.alternatives, "function": function,
            "record_ids": ",".join(r.record_id for r in records), "parameters": parameters,
            "provider_labels": dict(PROVIDERS), "next": safe_next(request, "/"),
        }, status=409)
    request.session[f"ai_next_{task.pk}"] = safe_next(request, "")
    return redirect("ai:task", pk=task.pk)


@researcher_required
def launch_from_session(request):
    ids = request.session.pop("ai_records", [])
    function = request.session.pop("ai_function", "duplicates")
    records = list(Record.objects.filter(record_id__in=ids))
    try:
        task = services.prepare_task(request.user, function, records=records,
                                     scope_label=f"{len(records)} notice(s) de la bibliothèque")
    except services.AIUnavailable as exc:
        return render(request, "ai/unavailable.html", {"error": str(exc), "reason": exc.reason,
                                                       "alternatives": exc.alternatives, "function": function,
                                                       "record_ids": ",".join(ids), "parameters": {},
                                                       "provider_labels": dict(PROVIDERS), "next": "/bibliotheque/"},
                      status=409)
    return redirect("ai:task", pk=task.pk)


@researcher_required
def task_detail(request, pk):
    task = get_object_or_404(AITask, pk=pk, user=request.user)
    profile = active_profile(request.user)
    if request.method == "POST" and task.status == "draft":
        if request.POST.get("action") == "cancel":
            task.status = "cancelled"
            task.save(update_fields=["status"])
            services.purge_payload_if_needed(task)
            messages.info(request, "Traitement annulé : rien n'a été envoyé.")
            return redirect(safe_url(request, request.session.pop(f"ai_next_{task.pk}", ""), "/"))
        if profile.batch_extra_confirmation and task.records.count() > 1 and not request.POST.get("confirm_batch"):
            messages.error(request, "Cochez la confirmation supplémentaire pour un traitement par lot.")
            return redirect("ai:task", pk=task.pk)
        try:
            services.confirm_and_dispatch(task, request.user)
            log_action(request, "ai.run", task, f"{task.get_function_display()} via {task.provider}/{task.model}",
                       records=task.records.count())
        except services.AIUnavailable as exc:
            messages.error(request, str(exc))
        return redirect("ai:task", pk=task.pk)
    task.refresh_from_db()
    if task.function == "query_extension" and task.status == "done":
        request.session["ai_variants"] = task.output.get("variants", [])
    return render(request, "ai/task.html", {
        "task": task, "profile": profile, "records": task.records.select_related("catalogue")[:50],
        "show_payload": profile.mode == "confirm",
        "next": request.session.get(f"ai_next_{task.pk}", ""),
        "spend": services.monthly_spend(request.user),
    })


@researcher_required
def tasks(request):
    qs = AITask.objects.filter(user=request.user)
    month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = qs.filter(created_at__gte=month).aggregate(tin=Sum("tokens_in"), tout=Sum("tokens_out"),
                                                       cost=Sum("cost_estimate"))
    return render(request, "ai/tasks.html", {"tasks": qs[:100], "usage": usage, "profile": active_profile(request.user)})


@admin_required
def prices(request):
    if request.method == "POST":
        if request.POST.get("delete"):
            AIModelPrice.objects.filter(pk=request.POST["delete"]).delete()
        else:
            try:
                AIModelPrice.objects.create(provider=request.POST["provider"], model_prefix=request.POST["model_prefix"].strip(),
                                            input_per_million=request.POST["input_per_million"],
                                            output_per_million=request.POST["output_per_million"])
                messages.success(request, "Tarif enregistré (sert uniquement aux estimations).")
            except Exception as exc:
                messages.error(request, f"Saisie invalide : {exc}")
        return redirect("ai:prices")
    return render(request, "ai/prices.html", {"prices": AIModelPrice.objects.all(), "providers": PROVIDERS})


# --------------------------------------------------------------------------- 2.0.0, lot 8 : choix du modèle


def _price_labels(provider):
    prices = list(AIModelPrice.objects.filter(provider=provider))

    def label(model_id):
        candidates = [p for p in prices if model_id.startswith(p.model_prefix)]
        if not candidates:
            return ""
        p = max(candidates, key=lambda c: len(c.model_prefix))
        return (f"≈ {p.input_per_million.normalize():f} $ / {p.output_per_million.normalize():f} $ "
                "par million de jetons")
    return label


def _picker_context(request, data, *, error=""):
    provider_field = data.get("provider_field", "")
    model_field = data.get("model_field", "")
    provider = data.get(provider_field, "") if provider_field else ""
    current = (data.get(model_field, "") if model_field else "").strip()
    ctx = {"provider": provider, "current": current, "error": error, "model_id": data.get("model_id", ""),
           "provider_id": data.get("provider_id", ""), "provider_field": provider_field, "model_field": model_field,
           "provider_label": dict(PROVIDERS).get(provider, "")}
    if provider not in dict(PROVIDERS):
        ctx["provider"] = ""
        return ctx
    if provider == "ollama":  # 2.0.0 (lot 4) : modèles installés dans l'IA locale (aucune clé, aucun coût)
        from django.utils import timezone

        from .local import credential_for, installed

        cred = credential_for(request.user)
        state_models = installed()
        if state_models != (cred.available_models or []):
            cred.available_models, cred.last_tested_at = state_models, timezone.now()
            cred.save(update_fields=["available_models", "last_tested_at"])
    else:
        cred = AIProviderCredential.objects.filter(user=request.user, provider=provider).first()
    ctx["credential"] = cred if cred and cred.is_configured else None
    if ctx["credential"] is None:
        return ctx
    label = (lambda model_id: "gratuit, sur cet ordinateur") if provider == "ollama" else _price_labels(provider)
    ids = text_models(provider, cred.available_models)
    ctx["models"] = [{"id": m, "price": label(m)} for m in ids]
    ctx["listed"] = current in ids
    ctx["missing"] = bool(current) and bool(ids) and current not in ids
    ctx["truncated"] = len(cred.available_models or []) >= MAX_STORED_MODELS
    return ctx


@researcher_required
def model_picker(request):
    """Liste déroulante des modèles du fournisseur choisi (fragment HTMX, sans appel au fournisseur)."""
    return render(request, "ai/_model_picker.html", _picker_context(request, request.GET))


@researcher_required
@require_POST
def model_refresh(request):
    """« Actualiser la liste » : interroge le fournisseur avec la clé de l'utilisateur, sur son action seulement."""
    provider = request.POST.get(request.POST.get("provider_field", ""), "")
    error = ""
    if provider == "ollama":  # 2.0.0 (lot 4) : la liste vient du service local (relue par _picker_context)
        return render(request, "ai/_model_picker.html", _picker_context(request, request.POST))
    cred = AIProviderCredential.objects.filter(user=request.user, provider=provider).first()
    if cred is not None and cred.is_configured:
        try:
            models = text_models(provider, get_provider(cred).list_models())
            cred.status, cred.last_error = "ok", ""
            cred.available_models = models[:MAX_STORED_MODELS]
        except (ProviderError, ImproperlyConfigured) as exc:
            # La liste précédente est conservée ; l'erreur est affichée, jamais masquée.
            cred.status, cred.last_error = "error", str(exc)[:500]
            error = f"Actualisation impossible : {exc}"
        cred.last_tested_at = timezone.now()
        cred.save()
        log_action(request, "ai.models_refreshed", cred, cred.get_provider_display())
    return render(request, "ai/_model_picker.html", _picker_context(request, request.POST, error=error))
