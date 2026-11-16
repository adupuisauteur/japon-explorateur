"""
IA locale gratuite (2.0.0, lot 4, demande U8) : service Ollama facultatif de J-ed.

- Le service ne démarre que si « ollama » figure dans COMPOSE_PROFILES (fichier .env) ; aucun port n'est publié.
- Aucun modèle n'est livré ni téléchargé d'office : l'utilisateur choisit un modèle dans une courte liste (taille
  affichée), confirme, puis J-ed le télécharge dans une tâche suivie et reprenable, et fait un résumé d'essai.
- J-ed lui parle comme à un service « compatible OpenAI » (adresse interne fixée par l'exploitant, OLLAMA_URL).
- Les tailles viennent de la bibliothèque Ollama (ollama.com/library), relevées le 15 novembre 2026.
"""
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
    return (getattr(settings, "OLLAMA_URL", "") or "").rstrip("/")


def _client(timeout):
    return httpx.Client(timeout=timeout, transport=getattr(settings, "OLLAMA_TRANSPORT", None))


def health():
    """(état, problème) : {"version", "models": [{"name", "size"}]} ou (None, message)."""
    if not base_url():
        return None, ("IA locale non configurée : adresse du service absente (OLLAMA_URL).")
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


def pull(model):
    """Télécharge un modèle (Ollama reprend un téléchargement interrompu). Retourne un message."""
    if model not in [m["model"] for m in CATALOGUE] and not getattr(settings, "OLLAMA_ALLOW_ANY_MODEL", False):
        raise ValueError("Modèle hors de la liste proposée.")
    try:
        with _client(settings.OLLAMA_PULL_TIMEOUT) as client:
            response = client.post(f"{base_url()}/api/pull", json={"model": model, "stream": False})
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Téléchargement interrompu ({exc.__class__.__name__}) : relancez, il reprendra.") from None
    if response.status_code >= 400:
        raise RuntimeError(f"Le service d'IA locale a refusé le téléchargement (HTTP {response.status_code}).")
    status = (response.json() or {}).get("status", "") if response.content else ""
    if status and status != "success":
        raise RuntimeError(f"Téléchargement inachevé : {status}.")
    return f"Modèle {model} installé."


def remove(model):
    with _client(60) as client:
        response = client.request("DELETE", f"{base_url()}/api/delete", json={"model": model})
    if response.status_code >= 400:
        raise RuntimeError(f"Suppression refusée par le service (HTTP {response.status_code}).")


def run_selftest(user, model):
    """Résumé d'essai d'un texte fictif ; résultat sur la page « Moteurs locaux » et « État »."""
    from apps.core.models import ServiceCheck

    from .providers import ProviderError, get_provider

    try:
        provider = get_provider(credential_for(user))
        completion = provider.complete(
            "Réponds uniquement par un objet JSON valide.",
            "Résume en français, en une phrase, ce texte japonais fictif. Format : {\"summary\": \"…\"}\n"
            + TEST_TEXT + ("\n/no_think" if model.startswith("qwen3") else ""), model, max_tokens=300)
        from apps.translation.summaries import parse

        text = parse(completion.text)["summary"]
    except (ProviderError, RuntimeError) as exc:
        return ServiceCheck.record(CHECK_NAME, False, f"Essai de résumé en échec : {exc}", model=model)
    return ServiceCheck.record(CHECK_NAME, True, f"IA locale prête — {model}.", model=model, summary=text[:400])


def last_selftest():
    from apps.core.models import ServiceCheck

    return ServiceCheck.objects.filter(name=CHECK_NAME).first()
