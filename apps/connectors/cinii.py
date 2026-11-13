"""
Connecteur CiNii Research (国立情報学研究所) — API OpenSearch officielle, réponse JSON-LD.

Documentation : https://support.nii.ac.jp/ja/cir/r_opensearch
- Adresse : https://cir.nii.ac.jp/opensearch/{type} avec type ∈ all, data, articles, books, dissertations, projects.
  Le type « books » couvre les livres et revues des bibliothèques universitaires (données CiNii Books).
- Paramètres : appid (obligatoire), format=json, q, title, creator, from/until (AAAA ou AAAAMM),
  count (1 à 200), start, sortorder (4 = pertinence), lang.
- Réponse : « items » (tableau) ; chaque élément : @id, title, link.@id, dc:creator (tableau),
  dc:type, dc:publisher, prism:publicationName, prism:publicationDate, description,
  dc:identifier (tableau {@type, @value}), dc:subject (tableau), dc:source (tableau {@id, dc:title} : texte intégral).

L'identifiant d'application (appid) est gratuit mais nominatif : il est lu dans la variable
d'environnement CINII_APPID (fichier .env), jamais enregistré en base, et masqué dans
tous les journaux et rapports.
"""
import time

from django.conf import settings

from .base import BaseConnector, ConnectorError, ConnectorNotConfigured, ConnectorResult, SearchResponse
from .http import ConnectorHTTP, format_error
from .japansearch import _first, _join
from .registry import register

ENDPOINT = "https://cir.nii.ac.jp/opensearch/{type}"
SEARCH_TYPES = ("all", "data", "articles", "books", "dissertations", "projects")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_cinii(payload):
    """Analyse une réponse JSON-LD. Retourne (résultats, total, avertissements)."""
    if not isinstance(payload, dict):
        raise format_error("Réponse CiNii inattendue (objet JSON attendu).", str(payload)[:300],
                           code="unexpected_structure")
    if "items" not in payload and "opensearch:totalResults" not in payload:
        raise format_error("Réponse CiNii inattendue (ni « items » ni « opensearch:totalResults ») : "
                           "le format de l'API a peut-être changé.", str(payload)[:300], code="unexpected_structure")
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise format_error("Réponse CiNii inattendue (« items » n'est pas une liste).", str(payload)[:300],
                           code="unexpected_structure")
    results, warnings = [], []
    for item in items:
        try:
            results.append(parse_cinii_item(item))
        except (ValueError, TypeError, AttributeError) as exc:
            warnings.append(f"Un résultat CiNii illisible a été ignoré ({exc}).")
    return results, _int(payload.get("opensearch:totalResults")), warnings


def parse_cinii_item(item):
    if not isinstance(item, dict):
        raise ValueError("élément non structuré")
    link = item.get("link")
    detail = (link.get("@id") if isinstance(link, dict) else _first(link)) or item.get("@id") or ""
    crid = str(item.get("@id") or detail).rstrip("/").rsplit("/", 1)[-1]
    if not crid:
        raise ValueError("identifiant absent")
    full_text = ""
    for src in item.get("dc:source") or []:
        if isinstance(src, dict) and str(src.get("@id", "")).startswith("http"):
            full_text = src["@id"]
            break
    identifiers = [f"{i.get('@type', '')}:{i.get('@value', '')}" for i in item.get("dc:identifier") or []
                   if isinstance(i, dict) and i.get("@value")]
    description = _first(item.get("description"))
    publication = " ; ".join(filter(None, [_first(item.get("prism:publicationName")), _first(item.get("dc:publisher"))]))
    if publication:
        description = (description + "\n" if description else "") + f"Publication : {publication}"
    data = {
        "source_id": crid,
        "source_url": detail if str(detail).startswith("http") else f"https://cir.nii.ac.jp/crid/{crid}",
        "original_title": _first(item.get("title")) or "(sans titre)",
        "creator_original": _join(item.get("dc:creator")),
        "copy_date_text": _first(item.get("prism:publicationDate") or item.get("dc:date")),
        "document_type_original": _first(item.get("dc:type")),
        "description_original": description,
        "subjects_original": _join(item.get("dc:subject")),
        "digital_access_url": full_text,
        "rights_and_access": "Texte intégral signalé par CiNii" if full_text else "",
    }
    raw = {k: v for k, v in item.items() if k != "@context"}
    if identifiers:
        raw["_identifiants"] = identifiers
    return ConnectorResult(source_id=crid, data=data, raw=raw, raw_format="cinii-jsonld")


@register
class CiNiiResearchConnector(BaseConnector):
    key = "cinii"
    label = "CiNii Research (国立情報学研究所)"
    description = ("Articles, livres des bibliothèques universitaires (CiNii Books), thèses, données et projets "
                   "de recherche japonais, via l'API OpenSearch officielle de CiNii Research.")
    supports_fielded_search = True
    supports_date_filter = True
    unsupported_fields = ["reading", "creator_reading", "composition_date_text", "holding_institution_text",
                          "shelfmark", "image_url"]
    config_help = {
        "search_type": "Type de recherche : all (défaut), books (bibliothèques universitaires), articles, "
                       "dissertations, data, projects.",
        "max_variants": "Nombre de variantes de graphie interrogées en plus du terme principal (défaut 3).",
        "lang": "Langue des métadonnées renvoyées : ja (défaut) ou en.",
    }

    def _appid(self):
        appid = getattr(settings, "CINII_APPID", "") or ""
        if not appid:
            raise ConnectorNotConfigured(
                "Identifiant d'application CiNii absent : demandez-le gratuitement à NII (inscription « CiNii API ») "
                "puis indiquez-le dans le fichier .env (CINII_APPID=…) et redémarrez l'application.")
        return appid

    def _params(self, query, text):
        params = {"appid": self._appid(), "format": "json", "lang": self.config.get("lang", "ja"),
                  "count": max(1, min(int(query.page_size or 20), 200)),
                  "start": (query.page - 1) * query.page_size + 1, "sortorder": 4}
        if text:
            params["q"] = text
        if query.title:
            params["title"] = query.title
        if query.creator:
            params["creator"] = query.creator
        if query.date_from:
            params["from"] = str(query.date_from)
        if query.date_to:
            params["until"] = str(query.date_to)
        if not any(k in params for k in ("q", "title", "creator")):
            raise ConnectorError("Requête vide : saisissez au moins un terme.", kind="query", code="empty_query")
        return params

    def search(self, query):
        started = time.monotonic()
        search_type = self.config.get("search_type", "all")
        if search_type not in SEARCH_TYPES:
            raise ConnectorNotConfigured(f"Type de recherche CiNii inconnu : « {search_type} ».")
        url = ENDPOINT.format(type=search_type)
        terms = query.all_terms()
        http = ConnectorHTTP(self.catalogue)
        payload = http.get_json(url, params=self._params(query, terms[0] if terms else ""))
        results, total, warnings = parse_cinii(payload)
        seen = {r.source_id for r in results}
        for variant in terms[1:1 + int(self.config.get("max_variants", 3))]:
            try:
                more, _, more_warnings = parse_cinii(http.get_json(url, params=dict(self._params(query, variant), start=1)))
            except ConnectorError as exc:
                warnings.append(f"Variante « {variant} » non interrogée : {exc}")
                continue
            warnings.extend(more_warnings)
            for r in more:
                if r.source_id not in seen:
                    seen.add(r.source_id)
                    results.append(r)
        return SearchResponse(results=results, total=total, page=query.page, warnings=warnings,
                              has_more=bool(total and query.page * query.page_size < total),
                              elapsed_ms=int((time.monotonic() - started) * 1000))
