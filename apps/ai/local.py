"""
IA locale gratuite (2.0.0, lot 4, demande U8) : service Ollama facultatif de J-ed.

- Le service ne démarre que si « ollama » figure dans COMPOSE_PROFILES (fichier .env) ; aucun port n'est publié.
- Aucun modèle n'est livré ni téléchargé d'office : l'utilisateur choisit un modèle dans une courte liste (taille
  affichée), confirme, puis J-ed le télécharge dans une tâche suivie et reprenable, et fait un résumé d'essai.
- J-ed lui parle comme à un service « compatible OpenAI » (adresse interne fixée par l'exploitant, OLLAMA_URL).
- Les tailles viennent de la bibliothèque Ollama (ollama.com/library), relevées le 15 novembre 2026.
"""
import json

from django.conf import settings

import httpx

from .models import AIProviderCredential

PROVIDER = "ollama"
CHECK_NAME = "ollama_essai"
#: modèles proposés : lisent le japonais et tiennent dans la mémoire accordée à Docker sur un poste ordinaire
CATALOGUE = [
    {"model": "qwen3:4b", "size": "2,5 Go", "memory": "environ 4 Go libres",
     "note": "Conseillé : bon compromis entre qualité et vitesse ; lit le japonais (famille Qwen, multilingue)."},
    {"model": "qwen3:8b", "size": "5,2 Go", "memory": "environ 7 Go libres",
     "note": "Meilleure qualité, nettement plus lent ; à éviter en même temps qu'Argos avec moins de 12 Go "
             "accordés à Docker."},
    {"model": "qwen3:1.7b", "size": "1,4 Go", "memory": "environ 3 Go libres",
     "note": "Très léger et rapide, mais qualité limitée : pour un poste à mémoire réduite."},
]
TEST_TEXT = ("書名：架空の旅日記。著者不詳。江戸時代後期の写本。京都から江戸までの道中を記した紀行文で、"
             "各宿場の様子や名所が記されている。")


def base_url():
    """Adresse du service, vide s'il n'est pas prévu : le profil « ollama » absent de COMPOSE_PROFILES (le fichier
    .env est transmis aux conteneurs) veut dire « IA locale non installée », pas « en panne »."""
    import os

    profiles = os.environ.get("COMPOSE_PROFILES")
    if profiles is not None and "ollama" not in [p.strip() for p in profiles.split(",")]:
        return ""
    return (getattr(settings, "OLLAMA_URL", "") or "").rstrip("/")


def _client(timeout):
    return httpx.Client(timeout=timeout, transport=getattr(settings, "OLLAMA_TRANSPORT", None))


def health():
    """(état, problème) : {"version", "models": [{"name", "size"}]} ou (None, message)."""
    if not base_url():
        return None, ("IA locale non installée : ajoutez « ollama » à la ligne COMPOSE_PROFILES du fichier .env "
                      "(par exemple COMPOSE_PROFILES=argos,ollama), puis lancez « docker compose up -d ».")
    try:
        with _client(10) as client:
            version = client.get(f"{base_url()}/api/version").json().get("version", "")
            tags = client.get(f"{base_url()}/api/tags").json().get("models") or []
    except (httpx.HTTPError, ValueError) as exc:
        return None, ("Service d'IA locale (Ollama) injoignable "
                      f"({exc.__class__.__name__}). Il ne démarre que si « ollama » figure dans la ligne "
                      "COMPOSE_PROFILES du fichier .env (par exemple COMPOSE_PROFILES=argos,ollama), puis "
                      "« docker compose up -d ».")
    models = [{"name": m.get("name") or m.get("model", ""), "size": m.get("size") or 0} for m in tags]
    return {"version": version, "models": models}, ""


def service_problem():
    state, problem = health()
    if state is None:
        return problem
    if not state["models"]:
        return ("Aucun modèle n'est installé pour l'IA locale : installez-en un dans Traduction → Moteurs locaux "
                "(section « IA locale »).")
    return ""


def installed(state=None):
    state = state or health()[0] or {}
    return [m["name"] for m in state.get("models", [])]


#: marqueur enregistré à la place d'une clé : l'IA locale n'en a pas, et ce marqueur n'est jamais déchiffré
NO_KEY = "ia-locale-sans-cle"


def credential_for(user):
    """Accès à l'IA locale pour cet utilisateur (aucune clé : le service local n'en demande pas)."""
    cred, _ = AIProviderCredential.objects.get_or_create(
        user=user, provider=PROVIDER, defaults={"encrypted_key": NO_KEY, "status": "ok"})
    if cred.encrypted_key != NO_KEY:
        cred.encrypted_key, cred.status = NO_KEY, "ok"
        cred.save(update_fields=["encrypted_key", "status"])
    return cred


def in_catalogue(model):
    return model in [m["model"] for m in CATALOGUE] or getattr(settings, "OLLAMA_ALLOW_ANY_MODEL", False)


def pull(model, progress=None):
    """Télécharge un modèle, en suivant la progression (Ollama reprend un téléchargement interrompu).

    ``progress(status, completed, total)`` est appelé à chaque étape annoncée par le service. Retourne un message.
    """
    if not in_catalogue(model):
        raise ValueError("Modèle hors de la liste proposée.")
    last = ""
    try:
        with _client(httpx.Timeout(60, read=600)) as client, client.stream(
                "POST", f"{base_url()}/api/pull", json={"model": model, "stream": True}) as response:
            if response.status_code >= 400:
                response.read()
                raise RuntimeError(f"Le service d'IA locale a refusé le téléchargement (HTTP {response.status_code}"
                                   f"{' : ' + response.text[:200] if response.text else ''}).")
            for line in response.iter_lines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("error"):
                    raise RuntimeError(f"Téléchargement refusé par le service : {event['error'][:300]}")
                last = event.get("status", last)
                if progress is not None:
                    progress(last, event.get("completed") or 0, event.get("total") or 0)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Téléchargement interrompu ({exc.__class__.__name__}) : reprenez-le, il repartira "
                           "de là où il s'est arrêté.") from None
    if last != "success":
        raise RuntimeError(f"Téléchargement inachevé{' (' + last + ')' if last else ''} : reprenez-le.")
    return f"Modèle {model} installé."


# --------------------------------------------------------------------------- tâche d'installation suivie

ITEM_PREFIX = "ollama:"


class LocalAIError(Exception):
    pass


def entry(model):
    return next((m for m in CATALOGUE if m["model"] == model), None)


def prepare_install(user, model):
    """Tâche suivie et reprenable (file « traduction ») : la confirmation a eu lieu dans le formulaire."""
    from django.utils import timezone

    from apps.translation.argos_packages import running_job
    from apps.translation.models import TranslationJob, TranslationJobItem

    item = entry(model)
    if item is None:
        raise LocalAIError("Modèle hors de la liste proposée.")
    state, problem = health()
    if state is None:
        raise LocalAIError(problem)
    if model in installed(state):
        raise LocalAIError(f"Le modèle {model} est déjà installé.")
    if running_job() is not None:
        raise LocalAIError("Une installation est déjà en cours : attendez sa fin.")
    job = TranslationJob.objects.create(
        user=user, kind="package", engine="ai", ai_provider=PROVIDER, ai_model=model, status="confirmed",
        confirmed_at=timezone.now(), total_items=1,
        scope_label=f"IA locale : téléchargement du modèle {model} ({item['size']})")
    TranslationJobItem.objects.create(job=job, position=0, record_field=ITEM_PREFIX + model)
    return job


def is_install_job(job):
    return job.kind == "package" and job.ai_provider == PROVIDER


def run_install_job(job):
    """Télécharge, puis fait un résumé d'essai. Progression enregistrée (élément de tâche, battement de cœur)."""
    from django.utils import timezone

    from apps.translation.argos_packages import _notify_end

    now = timezone.now()
    job.status, job.started_at, job.heartbeat_at = "running", job.started_at or now, now
    job.save(update_fields=["status", "started_at", "heartbeat_at"])
    for item in job.items.filter(status="pending").order_by("position"):
        model = item.record_field[len(ITEM_PREFIX):]
        seen = {"at": None}

        def progress(status, completed, total, item=item):
            moment = timezone.now()
            if seen["at"] and (moment - seen["at"]).total_seconds() < 5 and status != "success":
                return
            seen["at"] = moment
            pct = f" — {completed * 100 // total} %" if total else ""
            item.error_message = f"{status}{pct}"[:500]
            item.save(update_fields=["error_message", "updated_at"])
            type(job).objects.filter(pk=job.pk).update(heartbeat_at=moment)

        try:
            detail = pull(model, progress)
            item.status, item.error_kind, item.error_message = "done", "", detail
        except (RuntimeError, ValueError) as exc:
            item.status, item.error_kind, item.error_message = "failed", "service", str(exc)[:500]
        item.attempts += 1
        item.save(update_fields=["status", "error_kind", "error_message", "attempts", "updated_at"])
    statuses = list(job.items.values_list("status", flat=True))
    job.done_items, job.failed_items = statuses.count("done"), statuses.count("failed")
    job.status = "done" if job.failed_items == 0 else "failed"
    job.finished_at = job.heartbeat_at = timezone.now()
    job.error_summary = "Modèle non installé : voir le détail." if job.failed_items else ""
    job.save(update_fields=["status", "done_items", "failed_items", "finished_at", "heartbeat_at", "error_summary"])
    check = run_selftest(job.user, job.ai_model) if job.done_items and job.user_id else None
    _notify_end(job, check)


def remove(model):
    with _client(60) as client:
        response = client.request("DELETE", f"{base_url()}/api/delete", json={"model": model})
    if response.status_code >= 400:
        raise RuntimeError(f"Suppression refusée par le service (HTTP {response.status_code}).")


def run_selftest(user, model):
    """Résumé d'essai d'un texte fictif ; résultat sur la page « Moteurs locaux » et « État »."""
    from apps.core.models import ServiceCheck

    from .providers import ProviderError, get_provider

    from types import SimpleNamespace

    from apps.translation import summaries

    try:
        provider = get_provider(credential_for(user))
        # 16 novembre 2026 : l'ancienne consigne d'essai, plus courte que celle des vrais résumés, n'annonçait pas
        # le texte ; qwen3:4b répondait {"error": "No input text provided"}. L'essai reprend désormais exactement la
        # consigne d'un vrai résumé court (même système, même mise en forme, texte annoncé par « TEXTE : »).
        job = SimpleNamespace(options={"kind": "court", "language": "fr"}, ai_model=model, ai_provider=PROVIDER)
        prompt = summaries._build_prompt(job, TEST_TEXT, step="final")
        completion = provider.complete(summaries.SYSTEM, prompt, model,
                                       max_tokens=summaries.OUT_TOKENS["court"] * 2)
        text = summaries.parse(completion.text)["summary"]
    except (ProviderError, RuntimeError) as exc:
        return ServiceCheck.record(CHECK_NAME, False, f"Essai de résumé en échec : {exc}", model=model)
    return ServiceCheck.record(CHECK_NAME, True, f"IA locale prête — {model}.", model=model, summary=text[:400])


def last_selftest():
    from apps.core.models import ServiceCheck

    return ServiceCheck.objects.filter(name=CHECK_NAME).first()


AUTO_ATTEMPTS = 5


def auto_selftest(attempt=1):
    """Essai automatique après un démarrage (16 novembre 2026 : un essai en échec, fait avant un correctif, restait
    affiché « en échec » alors que l'IA locale fonctionnait). Rien si l'IA locale n'est pas installée, n'a aucun
    modèle, ou si le dernier essai a réussi avec un modèle toujours installé. Retourne « fait », « inutile »,
    « attente » ou « abandon »."""
    from apps.accounts.models import User

    if not base_url():
        return "inutile"
    state, _problem = health()
    if state is None:
        return "attente" if attempt < AUTO_ATTEMPTS else "abandon"
    names = installed(state)
    if not names:
        return "inutile"
    last = last_selftest()
    model = (last.data or {}).get("model") if last else None
    if last and last.ok and model in names:
        return "inutile"
    if model not in names:
        model = next((m["model"] for m in CATALOGUE if m["model"] in names), names[0])
    admin = User.objects.filter(role=User.ROLE_ADMIN, is_active=True).order_by("pk").first()
    if admin is None:
        return "inutile"
    run_selftest(admin, model)
    return "fait"
