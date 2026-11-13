"""Rapport de diagnostic exportable (§3.11) : lisible (Markdown) ou structuré (JSON), toujours expurgé.

Le rapport ne contient ni nom d'utilisateur, ni adresse IP, ni chemin personnel,
ni secret. Les termes de recherche peuvent être masqués à la demande.
"""
import json
import platform
import re

import django
from django.conf import settings
from django.utils import timezone

from apps.core.logging import redact, redact_mapping

from .services import before_after_fix

QUERY_KEYS = ("q", "keyword", "any", "title", "creator", "query", "terms", "query_terms")
_QUERY_IN_URL = re.compile(r"([?&](?:q|keyword|any|title|creator|q-contributor)=)([^&\s]*)")


def environment():
    return {
        "application_version": settings.APP_VERSION,
        "data_schema_version": settings.DATA_SCHEMA_VERSION,
        "python": platform.python_version(),
        "django": django.get_version(),
        "systeme_serveur": f"{platform.system()} {platform.release()}",
        "base_de_donnees": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
        "genere_le": timezone.localtime().isoformat(timespec="seconds"),
    }


def _hide_terms(value):
    if isinstance(value, dict):
        return {k: ("[termes masqués]" if k in QUERY_KEYS else _hide_terms(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_hide_terms(v) for v in value]
    if isinstance(value, str):
        value = _QUERY_IN_URL.sub(lambda m: m.group(1) + "[termes masqués]", value)
        return re.sub(r"« [^»]* »", "« [termes masqués] »", value)
    return value


def incident_payload(incident, *, hide_terms=False, max_occurrences=20):
    occurrences = [{
        "date": timezone.localtime(o.occurred_at).isoformat(timespec="seconds"), "version": o.app_version,
        "request_id": o.request_id, "http_status": o.http_status, "operation": o.operation,
        "message": o.message, "context": o.context,
    } for o in incident.occurrences.all()[:max_occurrences]]
    history = [{
        "date": timezone.localtime(e.at).isoformat(timespec="seconds"), "evenement": e.get_kind_display(),
        "de": e.get_from_status_display() if e.from_status else "", "vers": e.get_to_status_display() if e.to_status else "",
        "commentaire": e.comment, "version": e.app_version,
    } for e in incident.events.all()]
    cmp = before_after_fix(incident)
    payload = {
        "identifiant": incident.uid,
        "resume": incident.title,
        "module": incident.get_module_display(),
        "source": incident.source_code,
        "categorie": incident.get_category_display(),
        "gravite": incident.get_severity_display(),
        "origine_probable": incident.get_origin_display(),
        "statut": incident.get_status_display(),
        "signalement_manuel": incident.is_manual,
        "operation": incident.operation,
        "message": incident.message,
        "code_technique": incident.technical_code,
        "code_http": incident.http_status,
        "dernier_identifiant_de_requete": incident.last_request_id,
        "premiere_occurrence": timezone.localtime(incident.first_seen_at).isoformat(timespec="seconds"),
        "derniere_occurrence": timezone.localtime(incident.last_seen_at).isoformat(timespec="seconds"),
        "nombre_occurrences": incident.occurrence_count,
        "version_premiere_occurrence": incident.first_seen_version,
        "version_derniere_occurrence": incident.last_seen_version,
        "corrige_dans_la_version": incident.fixed_in_version,
        "reapparitions_apres_correction": incident.reappeared_count,
        "contexte": incident.context,
        "etapes_pour_reproduire": reproduction_steps(incident),
        "resultat_attendu": incident.expected,
        "resultat_obtenu": incident.obtained,
        "capture_jointe": bool(incident.screenshot),
        "avant_apres_correction": ({"corrige_le": timezone.localtime(cmp["fixed_at"]).isoformat(timespec="seconds"),
                                    "occurrences_avant": cmp["before"], "occurrences_apres": cmp["after"]}
                                   if cmp else None),
        "occurrences_recentes": occurrences,
        "historique": history,
    }
    payload = redact_mapping(payload)
    return _hide_terms(payload) if hide_terms else payload


def reproduction_steps(incident):
    if incident.is_manual and incident.steps:
        return incident.steps
    ctx = incident.context or {}
    steps = []
    if incident.module == "recherche" and incident.source_code:
        steps.append("Ouvrir « Rechercher ».")
        steps.append(f"Cocher uniquement la source « {incident.source_code} ».")
        if ctx.get("query_terms"):
            steps.append(f"Lancer la recherche « {ctx['query_terms']} ».")
        else:
            steps.append("Relancer la recherche indiquée dans « Opération en cours ».")
    elif incident.module in ("connecteur", "metadonnees") and incident.source_code:
        steps.append(f"Ouvrir « Sources », puis la source « {incident.source_code} ».")
        steps.append("Cliquer sur « Tester le connecteur » ou relancer l'actualisation.")
    elif ctx.get("path"):
        steps.append(f"Ouvrir la page {ctx['path']} (méthode {ctx.get('method', 'GET')}).")
    if not steps:
        return "Non déterminées automatiquement : voir « Opération en cours »."
    return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))


def build_json(incidents, *, hide_terms=False, filters=None):
    data = {"rapport": "Journal des dysfonctionnements — Japon · Explorateur documentaire",
            "environnement": environment(), "filtres": filters or {},
            "incidents": [incident_payload(i, hide_terms=hide_terms) for i in incidents]}
    return redact(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def build_markdown(incidents, *, hide_terms=False, filters=None):
    env = environment()
    lines = ["# Rapport de diagnostic — Japon · Explorateur documentaire", "",
             f"- Version de l'application : **{env['application_version']}** (schéma de données {env['data_schema_version']})",
             f"- Généré le : {env['genere_le']}",
             f"- Environnement : Python {env['python']}, Django {env['django']}, {env['systeme_serveur']}, "
             f"base {env['base_de_donnees']}",
             f"- Termes de recherche : {'masqués' if hide_terms else 'inclus'}"]
    if filters:
        lines.append("- Filtres : " + ", ".join(f"{k} = {v}" for k, v in filters.items() if v))
    lines += ["", "> Rapport expurgé automatiquement : aucun mot de passe, clé API, jeton, nom d'utilisateur ni "
                  "chemin personnel. Relisez-le avant de le transmettre.", ""]
    for incident in incidents:
        p = incident_payload(incident, hide_terms=hide_terms)
        lines += [f"## {p['identifiant']} — {p['resume']}", "",
                  "| Élément | Valeur |", "|---|---|"]
        for label, key in [("Module", "module"), ("Source", "source"), ("Catégorie", "categorie"),
                           ("Gravité", "gravite"), ("Origine probable", "origine_probable"), ("Statut", "statut"),
                           ("Opération en cours", "operation"), ("Code technique", "code_technique"),
                           ("Code HTTP", "code_http"), ("Dernier identifiant de requête", "dernier_identifiant_de_requete"),
                           ("Première occurrence", "premiere_occurrence"), ("Dernière occurrence", "derniere_occurrence"),
                           ("Occurrences", "nombre_occurrences"), ("Version (1re / dernière)", None),
                           ("Corrigé dans la version", "corrige_dans_la_version"),
                           ("Réapparitions après correction", "reapparitions_apres_correction")]:
            value = (f"{p['version_premiere_occurrence']} / {p['version_derniere_occurrence']}" if key is None
                     else p.get(key))
            if value not in (None, "", 0) or key in ("nombre_occurrences",):
                lines.append(f"| {label} | {str(value).replace('|', '/')} |")
        lines += ["", "**Message**", "", "```", p["message"] or "(aucun)", "```", "",
                  "**Étapes pour reproduire**", "", p["etapes_pour_reproduire"], ""]
        if p["resultat_attendu"] or p["resultat_obtenu"]:
            lines += [f"**Résultat attendu** : {p['resultat_attendu']}", "",
                      f"**Résultat obtenu** : {p['resultat_obtenu']}", ""]
        if p["avant_apres_correction"]:
            c = p["avant_apres_correction"]
            lines += [f"**Avant / après correction** (corrigé le {c['corrige_le']}) : "
                      f"{c['occurrences_avant']} occurrence(s) avant, {c['occurrences_apres']} après.", ""]
        lines += ["**Contexte technique**", "", "```json",
                  json.dumps(p["contexte"], ensure_ascii=False, indent=2, default=str), "```", ""]
        if p["occurrences_recentes"]:
            lines += ["**Occurrences récentes**", "", "| Date | Version | Requête | HTTP | Message |", "|---|---|---|---|---|"]
            for o in p["occurrences_recentes"][:10]:
                msg = (o["message"] or "").replace("|", "/").replace("\n", " ")[:120]
                lines.append(f"| {o['date']} | {o['version']} | {o['request_id']} | {o['http_status'] or ''} | {msg} |")
            lines.append("")
        if p["historique"]:
            lines += ["**Historique**", ""]
            for h in p["historique"]:
                change = f" ({h['de']} → {h['vers']})" if h["de"] or h["vers"] else ""
                lines.append(f"- {h['date']} · {h['evenement']}{change}{' — ' + h['commentaire'] if h['commentaire'] else ''}")
            lines.append("")
    return redact("\n".join(lines))
