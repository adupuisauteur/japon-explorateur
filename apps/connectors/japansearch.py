"""
Connecteur Japan Search (ジャパンサーチ), agrégateur national de métadonnées patrimoniales.

API web simple publique, sans clé (documentation officielle :
https://jpsearch.go.jp/static/developer/webapi/ — chapitres 2 à 6) :
- recherche d'items : /api/item/search/jps-cross ; `keyword` répétable (ET par
  défaut, OU si chaque terme est préfixé par « + ») ; `size` ≤ 500 ; `from` ;
  filtre par base `f-db` ; personne/organisme `q-contributor` ; période `r-tempo=début,fin` ;
- recherche des bases connectées : /api/database/search (identifiant, nom, institution, apiType).

Seules les métadonnées dont l'institution autorise la diffusion par API sont servies.
Les noms de paramètres restent configurables au cas où l'API évoluerait.
Correctifs 1.2.0 : variantes combinées en OU (et non plus en ET), champs conformes à la
documentation (titleYomi, location, iiifUrl, provider…), filtre de dates documenté,
réponses illisibles classées comme telles.
"""
import time

from .base import BaseConnector, ConnectorError, ConnectorNotConfigured, ConnectorResult, SearchResponse
from .http import ConnectorHTTP, format_error
from .registry import register

DEFAULT_ENDPOINT = "https://jpsearch.go.jp/api/item/search/jps-cross"
DATABASE_SEARCH_ENDPOINT = "https://jpsearch.go.jp/api/database/search"
ITEM_PAGE = "https://jpsearch.go.jp/item/{id}"


def _first(value):
    if isinstance(value, list):
        return _first(value[0]) if value else ""
    if isinstance(value, dict):
        for k in ("value", "@value", "ja", "name", "label", "title"):
            if k in value:
                return _first(value[k])
        return ""
    return "" if value is None else str(value)


def _join(value, sep=" ; "):
    if isinstance(value, list):
        return sep.join(filter(None, (_first(v) for v in value)))
    return _first(value)


def _common(item):
    common = item.get("common") or {}
    if isinstance(common, list):  # la documentation décrit parfois « common » comme un tableau d'objets
        common = next((c for c in common if isinstance(c, dict)), {})
    return common if isinstance(common, dict) else {}


def parse_item(item, *, prefer_kokusho_id=False):
    """Transforme un élément Japan Search en ConnectorResult (champs absents = vides)."""
    import re

    if not isinstance(item, dict):
        raise ValueError("élément de résultat non structuré")
    common = _common(item)
    link = _first(common.get("linkUrl") or item.get("linkUrl"))
    title = _first(common.get("title") or item.get("title"))
    source_id = str(item.get("id") or common.get("id") or "")
    if prefer_kokusho_id and link:
        m = re.search(r"kokusho\.nijl\.ac\.jp/biblio/(\d+)", link) or re.search(r"10\.20730/(\d+)", link)
        if m:
            source_id = m.group(1)
    iiif = _first(common.get("iiifUrl") or common.get("iiifManifestUrl"))
    contents = _first(common.get("contentsUrl"))
    data = {
        "source_id": source_id,
        "source_url": link if link.startswith("http") else (ITEM_PAGE.format(id=source_id) if source_id else ""),
        "original_title": title or "(sans titre)",
        "reading": _first(common.get("titleYomi")),
        "creator_original": _join(common.get("contributor")),
        "description_original": _join(common.get("description"), "\n"),
        "copy_date_text": _join(common.get("temporal")),
        "holding_institution_text": _first(common.get("provider") or common.get("ownerOrg") or common.get("owner")),
        "subjects_original": _join(common.get("subCategory") or common.get("subject") or common.get("keyword")),
        "place_original": _join(common.get("location") or common.get("spatial")),
        "rights_and_access": _join(common.get("contentsRightsType") or common.get("rights")),
        "image_url": iiif or contents or _first(common.get("thumbnailUrl")),
        "digital_access_url": contents if contents.startswith("http") and not iiif else "",
        "document_type_original": _join(common.get("contentsType") or common.get("category") or common.get("type")),
        "source_updated_at": _first(item.get("modified") or common.get("modified")),
    }
    return ConnectorResult(source_id=source_id, data=data, raw=item, raw_format="jpsearch-json")


def keyword_values(query):
    """Termes à transmettre : un seul terme tel quel ; plusieurs (requête + variantes) préfixés par « + » = OU."""
    terms = [t for t in query.all_terms() if t]
    if not terms and query.title:
        terms = [query.title]
    if len(terms) <= 1:
        return terms
    return [t if t.startswith(("+", "-")) else f"+{t}" for t in terms]


def jpsearch_query(http, config, query, *, database=None):
    params = {
        config.get("size_param", "size"): min(int(query.page_size or 20), 500),
        config.get("from_param", "from"): (query.page - 1) * query.page_size,
    }
    keywords = keyword_values(query)
    if keywords:
        params[config.get("keyword_param", "keyword")] = keywords if len(keywords) > 1 else keywords[0]
    if query.creator:
        params[config.get("contributor_param", "q-contributor")] = query.creator
    if query.title and query.all_terms():
        # Pas de paramètre « titre » documenté : le titre s'ajoute aux mots-clés (combinaison ET).
        existing = params.get(config.get("keyword_param", "keyword"))
        params[config.get("keyword_param", "keyword")] = ([existing] if isinstance(existing, str) else existing) + [query.title]
    if database:
        params[config.get("db_param", "f-db")] = database
    if query.date_from or query.date_to:
        params[config.get("date_param", "r-tempo")] = f"{query.date_from or ''},{query.date_to or ''}"
    if not any(k in params for k in (config.get("keyword_param", "keyword"), config.get("contributor_param", "q-contributor"))):
        raise ConnectorError("Requête vide : saisissez au moins un terme.", kind="query", code="empty_query")
    payload = http.get_json(config.get("endpoint", DEFAULT_ENDPOINT), params=params)
    if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
        raise format_error("Format de réponse Japan Search inattendu (liste de résultats absente) : "
                           "l'API a peut-être changé.", str(payload)[:300], code="unexpected_structure")
    return payload


def parse_payload(payload, *, prefer_kokusho_id=False):
    """Analyse une page de résultats. Les éléments isolés illisibles sont ignorés et signalés en avertissement."""
    results, warnings = [], []
    for item in payload.get("list") or []:
        try:
            results.append(parse_item(item, prefer_kokusho_id=prefer_kokusho_id))
        except (ValueError, TypeError, AttributeError) as exc:
            warnings.append(f"Un résultat illisible a été ignoré ({exc}).")
    return results, warnings


def search_databases(http, keyword):
    """Bases connectées à Japan Search correspondant à un mot-clé (nom de l'institution ou de la collection)."""
    payload = http.get_json(DATABASE_SEARCH_ENDPOINT, params={"keyword": keyword, "size": 50})
    if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
        raise format_error("Liste des bases Japan Search illisible.", str(payload)[:300], code="unexpected_structure")
    out = []
    for db in payload.get("list") or []:
        if not isinstance(db, dict) or not db.get("id"):
            continue
        name = db.get("name") or {}
        out.append({
            "id": str(db["id"]),
            "name": (name.get("ja") or name.get("en") or db["id"]) if isinstance(name, dict) else str(name),
            "name_en": name.get("en", "") if isinstance(name, dict) else "",
            "provider": db.get("provider") or "",
            "records": db.get("recordCount"),
            "api_ok": db.get("apiType") == "ok",
            "url": db.get("url") or "",
        })
    return out


@register
class JapanSearchConnector(BaseConnector):
    key = "japansearch"
    label = "Japan Search"
    description = ("Recherche transversale via l'API publique de Japan Search ; peut être restreinte à une base "
                   "(archives, universités, musées…) par le paramètre « database ».")
    supports_fielded_search = True
    supports_date_filter = True
    unsupported_fields = ["creator_reading", "composition_date_text", "shelfmark"]
    config_help = {
        "database": "Identifiant de base Japan Search à filtrer (ex. najda pour les Archives nationales). "
                    "Utilisez « Trouver une base Japan Search » sur la fiche de la source Japan Search.",
        "endpoint": "Adresse de l'API de recherche transversale (par défaut celle de Japan Search).",
        "db_param": "Nom du paramètre de filtre par base (défaut : f-db).",
        "date_param": "Nom du paramètre de période (défaut : r-tempo).",
    }

    def search(self, query):
        database = self.config.get("database") or None
        if database is None and self.catalogue.code != "japansearch":
            # 16 novembre 2026 (-AvecSources sur le poste de l'utilisateur) : « Waseda » relié à Japan Search sans
            # identifiant de base renvoyait tout le portail (87 797 résultats, les mêmes que Japan Search).
            raise ConnectorNotConfigured(
                f"« {self.catalogue.name} » passe par Japan Search sans identifiant de base : elle renverrait tout le "
                "portail. Choisissez sa base (Sources → Japan Search → « Trouver une base Japan Search »), "
                "ou rendez-la au mode « import de fichiers ».")
        started = time.monotonic()
        http = ConnectorHTTP(self.catalogue)
        payload = jpsearch_query(http, self.config, query, database=database)
        results, warnings = parse_payload(payload)
        total = payload.get("hit") if isinstance(payload.get("hit"), int) else None
        return SearchResponse(results=results, total=total, page=query.page, warnings=warnings,
                              has_more=total is not None and query.page * query.page_size < total,
                              elapsed_ms=int((time.monotonic() - started) * 1000))
