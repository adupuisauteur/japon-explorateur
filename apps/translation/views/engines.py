"""
Traduction → Moteurs : lieu UNIQUE du choix des moteurs de traduction (décision « point unique »).

- DeepL et Google : clé saisie ici, chiffrée, jamais réaffichée ; test sans texte réel quand c'est possible.
- Argos : activation (simulation seulement en mode démonstration, réglage de l'administrateur : décision D4).
- IA : état lu dans le module IA ; les clés restent dans IA → Fournisseurs.
Enregistrer un réglage ne lance jamais de traduction.
"""
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.ai.crypto import encrypt_secret, encryption_available
from apps.ai.models import PROVIDERS as AI_PROVIDERS
from apps.ai.models import AIProviderCredential
from apps.ai.preferences import active_profile
from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from ..engines.base import TranslationEngineError
from ..engines.registry import ENGINE_CLASSES, get_engine
from .. import argos_packages, terms
from ..forms import EngineSettingForm, PreferenceForm
from ..journal import record_translation_error
from ..models import SETTING_ENGINES, EngineSetting

KEY_HELP = {
    "deepl": "Clé de l'API DeepL (compte DeepL API, offre gratuite ou payante).",
    "google_basic": "Clé d'API Google Cloud, restreinte à l'API Cloud Translation.",
}


def preference_for(user):
    from ..services import ensure_preference

    return ensure_preference(user)


@researcher_required
def engines(request):
    user = request.user
    settings_by_engine = {s.engine: s for s in EngineSetting.objects.filter(user=user)}
    rows = []
    for code, label in SETTING_ENGINES:
        setting = settings_by_engine.get(code)
        engine = get_engine(code, user)
        initial = {"enabled": setting.enabled if setting else True}
        if setting:
            initial.update({"plan": setting.plan, "monthly_char_cap": setting.monthly_char_cap})
        rows.append({"code": code, "label": label, "setting": setting, "status": engine.status(),
                     "form": EngineSettingForm(engine=code, initial=initial), "help": KEY_HELP.get(code, ""),
                     "cls": ENGINE_CLASSES[code]})
    credentials = {c.provider: c for c in AIProviderCredential.objects.filter(user=user)}
    profile = active_profile(user)
    ai_rows = []
    for code, label in AI_PROVIDERS:
        cred = credentials.get(code)
        engine = get_engine("ai", user, ai_provider=code, ai_model="(modèle)")
        ai_rows.append({"code": code, "label": label, "credential": cred, "status": engine.status(),
                        "models": (cred.available_models if cred else [])[:300]})
    pref = preference_for(user)
    return render(request, "translation/engines.html", {
        "rows": rows, "ai_rows": ai_rows, "profile": profile, "pref": pref,
        "pref_form": PreferenceForm(instance=pref), "encryption_ok": encryption_available(),
        "default_status": _choice_status(user, pref, "default"), "second_status": _choice_status(user, pref, "second"),
        "provider_terms": [dict(t, read=terms.acknowledged(user, t["key"])) for t in terms.all_terms()],
        "argos_invite": argos_packages.invite(user),
    })


def _choice_status(user, pref, prefix):
    code = getattr(pref, f"{prefix}_engine")
    if not code:
        return None
    engine = get_engine(code, user, ai_provider=getattr(pref, f"{prefix}_ai_provider"),
                        ai_model=getattr(pref, f"{prefix}_ai_model"))
    return {"name": engine.display_name, "status": engine.status()}


@researcher_required
@require_POST
def engine_save(request, code):
    if code not in dict(SETTING_ENGINES):
        return redirect("translation:engines")
    user = request.user
    setting, _ = EngineSetting.objects.get_or_create(user=user, engine=code)
    action = request.POST.get("action", "save")
    label = setting.get_engine_display()
    if action == "revoke":
        setting.encrypted_key = ""
        setting.status = "revoked"
        setting.quota_info = {}
        setting.save()
        log_action(request, "translation.key_revoked", setting, label)
        messages.info(request, f"Clé {label} effacée du serveur.")
        return redirect("translation:engines")
    if action == "test":
        engine = get_engine(code, user)
        try:
            message = engine.test()
            setting.status, setting.last_error = "ok", ""
            messages.success(request, message)
        except TranslationEngineError as exc:
            setting.status, setting.last_error = "error", str(exc)[:500]
            record_translation_error(exc, engine=code, operation="Test du moteur depuis Traduction → Moteurs")
            messages.error(request, f"Échec du test : {exc}")
        except ImproperlyConfigured as exc:
            setting.status, setting.last_error = "error", str(exc)[:500]
            messages.error(request, str(exc))
        setting.last_tested_at = timezone.now()
        setting.save()
        return redirect("translation:engines")
    form = EngineSettingForm(request.POST, engine=code)
    if not form.is_valid():
        messages.error(request, "Réglage invalide : " + "; ".join(e for errs in form.errors.values() for e in errs))
        return redirect("translation:engines")
    key = form.cleaned_data.get("api_key") or ""
    if key:
        try:
            setting.encrypted_key = encrypt_secret(key)
        except ImproperlyConfigured as exc:
            messages.error(request, str(exc))
            return redirect("translation:engines")
        setting.status = "untested"
        setting.quota_info = {}
    if "plan" in form.cleaned_data:
        if form.cleaned_data["plan"] != setting.plan:
            setting.status = "untested" if setting.has_key else setting.status
        setting.plan = form.cleaned_data["plan"]
    setting.monthly_char_cap = form.cleaned_data.get("monthly_char_cap")
    setting.enabled = bool(form.cleaned_data.get("enabled"))
    setting.save()
    log_action(request, "translation.engine_saved", setting,
               f"{label} : {'clé enregistrée (chiffrée), ' if key else ''}actif={setting.enabled}")
    messages.success(request, f"Réglage {label} enregistré." + (" Clé chiffrée ; elle ne sera plus affichée. "
                                                                "Testez la connexion." if key else "")
                     + " Aucune traduction n'a été lancée.")
    return redirect("translation:engines")


@researcher_required
@require_POST
def preferences_save(request):
    pref = preference_for(request.user)
    form = PreferenceForm(request.POST, instance=pref)
    if form.is_valid():
        form.save()
        log_action(request, "translation.preferences", pref,
                   f"Moteur par défaut : {pref.default_engine or '—'} ; deuxième : {pref.second_engine or '—'}")
        messages.success(request, "Choix des moteurs enregistré. Aucune traduction n'a été lancée.")
    else:
        messages.error(request, "Choix non enregistré : "
                       + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect("translation:engines")
