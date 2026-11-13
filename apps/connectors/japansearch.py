"""
Connecteur Japan Search (ジャパンサーチ), agrégateur national de métadonnées patrimoniales.

Utilise l'API web simple publique de Japan Search (recherche transversale,
réponses JSON). Les noms de paramètres sont configurables car l'API peut évoluer :
vérifier la documentation officielle (https://jpsearch.go.jp/api) avant activation.
"""
import re
import time

from .base import BaseConnector, ConnectorError, ConnectorResult, SearchResponse
from .http import ConnectorHTTP
from .registry import register

DEFAULT_ENDPOINT = "https://jpsearch.go.jp/api/item/search/jps-cross"


def _first(value):
    if isinstance(value, list):
        return _first(value[0]) if value else ""
    if isinstance(value, dict):
        for k in ("value", "@value", "name", "label", "ja", "title"):
            if k in value:
                return _first(value[k])
        return ""
    return "" if value is None else str(value)


def _join(value, sep=" ; "):
    if isinstance(value, list):
        return sep.join(filter(None, (_first(v) for v in value)))
    return _first(value)


def parse_item(item, *, prefer_kokusho_id=False):
    """Transforme un élément Japan Search en ConnectorResult (champs absents = vides)."""
    common = item.get("common") or {}
    link = _first(common.get("linkUrl") or item.get("linkUrl"))
    title = _first(common.get("title") or item.get("title"))
    source_id = str(item.get("id") or "")
    if prefer_kokusho_id and link:
        m = re.search(r"kokusho\.nijl\.ac\.jp/biblio/(\d+)", link) or re.search(r"10\.20730/(\d+)", link)
        if m:
            source_id = m.group(1)
    temporal = _join(common.get("temporal"))
    data = {
        "source_id": source_id,
        "source_url": link if link.startswith("http") else "",
        "original_title": title or "(sans titre)",
        "creator_original": _join(common.get("contributor")),
        "description_original": _join(common.get("description"), "\n"),
        "copy_date_text": temporal,
        "holding_institution_text": _first(common.get("provider") or common.get("owner")),
        "subjects_original": _join(common.get("subject") or common.get("keyword")),
        "place_original": _join(common.get("spatial")),
        "rights_and_access": _join(common.get("contentsRightsType") or common.get("rights")),
        "image_url": _first(common.get("contentsUrl") or common.get("iiifManifestUrl") or common.get("thumbnailUrl")),
        "document_type_original": _join(common.get("type")),
        "source_updated_at": _first(item.get("modified") or common.get("modified")),
    }
    return ConnectorResult(source_id=source_id, data=data, raw=item, raw_format="jpsearch-json")


def jpsearch_query(http, config, query, *, database=None):
    params = {
        config.get("keyword_param", "keyword"): " ".join(query.all_terms()) or query.title or query.creator,
        config.get("size_param", "size"): query.page_size,
        config.get("from_param", "from"): (query.page - 1) * query.page_size,
    }
    if database:
        params[config.get("db_param", "f-db")] = database
    # Filtre de dates transmis seulement si le paramètre a été vérifié et configuré.
    if query.date_from and config.get("date_param"):
        params[config["date_param"]] = f"{query.date_from},{query.date_to or ''}"
    return http.get_json(config.get("endpoint", DEFAULT_ENDPOINT), params=params)


@register
class JapanSearchConnector(BaseConnector):
    key = "japansearch"
    label = "Japan Search"
    description = "Recherche transversale via l'API publique de Japan Search."
    unsupported_fields = ["reading", "creator_reading", "composition_date_text", "shelfmark"]
    config_help = {
        "endpoint": "Adresse de l'API de recherche transversale (par défaut celle de Japan Search).",
        "database": "Identifiant de base à filtrer (facultatif).",
        "db_param": "Nom du paramètre de filtre par base (défaut : f-db).",
    }

    def search(self, query):
        started = time.monotonic()
        http = ConnectorHTTP(self.catalogue)
        payload = jpsearch_query(http, self.config, query, database=self.config.get("database") or None)
        items = payload.get("list") or payload.get("items") or []
        if not isinstance(items, list):
            raise ConnectorError("Format de réponse Japan Search inattendu.")
        results = [parse_item(i) for i in items]
        total = payload.get("hit") if isinstance(payload.get("hit"), int) else None
        return SearchResponse(results=results, total=total, page=query.page,
                              has_more=total is not None and query.page * query.page_size < total,
                              elapsed_ms=int((time.monotonic() - started) * 1000))
