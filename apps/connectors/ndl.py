"""
Connecteur NDL Search (国立国会図書館サーチ) — API OpenSearch officielle.
Documentation : https://ndlsearch.ndl.go.jp/help/api/specifications
Réponse RSS 2.0 enrichie (dc, dcterms, dcndl, openSearch).
"""
import time

from lxml import etree

from .base import BaseConnector, ConnectorError, ConnectorResult, SearchResponse
from .http import ConnectorHTTP, format_error
from .registry import register

ENDPOINT = "https://ndlsearch.ndl.go.jp/api/opensearch"
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
    "openSearch": "http://a9.com/-/spec/opensearchrss/1.0/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}
RDF_RESOURCE = f"{{{NS['rdf']}}}resource"


def _see_also(item):
    """Liens rdfs:seeAlso (attribut rdf:resource) : notice d'origine, collections numérisées, manifeste IIIF."""
    out = []
    for e in item.findall("rdfs:seeAlso", NS):
        url = (e.get(RDF_RESOURCE) or e.text or "").strip()
        if url.startswith("http"):
            out.append(url)
    return out


def _texts(item, path):
    return [(e.text or "").strip() for e in item.findall(path, NS) if (e.text or "").strip()]


def parse_opensearch(xml_text):
    if not (xml_text or "").strip():
        raise format_error("Réponse NDL vide.", xml_text, code="empty_body")
    try:
        root = etree.fromstring(xml_text.encode("utf-8"), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise format_error("Réponse NDL illisible (XML invalide).", xml_text, code="invalid_xml") from exc
    channel = root.find("channel")
    if channel is None:
        raise format_error("Réponse NDL inattendue (canal RSS absent) : le format de l'API a peut-être changé.",
                           xml_text, code="unexpected_structure")
    total_el = channel.find("openSearch:totalResults", NS)
    total = int(total_el.text) if total_el is not None and (total_el.text or "").isdigit() else None
    results = []
    for item in channel.findall("item"):
        bib_ids = [e.text for e in item.findall("dc:identifier", NS)
                   if e.get(f"{{{NS['xsi']}}}type", "").endswith("NDLBibID") and e.text]
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        source_id = bib_ids[0] if bib_ids else (guid or link)
        title = (_texts(item, "dc:title") or [item.findtext("title") or ""])[0]
        raw = {child.tag.split("}")[-1] + (f"[{child.get(f'{{{NS['xsi']}}}type')}]"
                                            if child.get(f"{{{NS['xsi']}}}type") else ""): (child.text or "").strip()
               for child in item}
        see_also = _see_also(item)
        digital = next((u for u in see_also if "dl.ndl.go.jp" in u or "/digimeta/" in u), "")
        iiif = next((u for u in see_also if "iiif" in u.lower() and "manifest" in u.lower()), "")
        data = {
            "source_id": source_id,
            "source_url": link if link.startswith("http") else "",
            "digital_access_url": digital,
            "image_url": iiif,
            "original_title": title.strip() or "(sans titre)",
            "reading": " ".join(_texts(item, "dcndl:titleTranscription")),
            "creator_original": " ; ".join(_texts(item, "dc:creator")) or (item.findtext("author") or ""),
            "creator_reading": " ; ".join(_texts(item, "dcndl:creatorTranscription")),
            "copy_date_text": " ; ".join(_texts(item, "dcterms:issued") or _texts(item, "dc:date")),
            "subjects_original": " ; ".join(_texts(item, "dc:subject")),
            "material_type_original": " ; ".join(_texts(item, "dcndl:materialType") or _texts(item, "category")),
            "description_original": " ; ".join(_texts(item, "dc:description")),
            "holding_institution_text": "国立国会図書館",
            "place_original": " ; ".join(_texts(item, "dcndl:publicationPlace")),
            "language": "ja",
        }
        if see_also:
            raw["seeAlso"] = see_also
        results.append(ConnectorResult(source_id=source_id, data=data, raw=raw, raw_format="ndl-opensearch"))
    return results, total


@register
class NDLConnector(BaseConnector):
    key = "ndl"
    label = "NDL Search (国立国会図書館サーチ)"
    description = "Catalogue de la Bibliothèque nationale de la Diète via l'API OpenSearch officielle."
    supports_fielded_search = True
    supports_date_filter = True
    unsupported_fields = ["translated_title", "composition_date_text", "rights_and_access"]
    config_help = {"extra_params": "Paramètres OpenSearch supplémentaires (ex. {\"mediatype\": \"1\"}).",
                   "max_count": "Nombre maximal de résultats par page (défaut 20, maximum 500).",
                   "max_variants": "Nombre de variantes de graphie interrogées en plus du terme principal (défaut 3)."}

    def search(self, query):
        started = time.monotonic()
        params = {"cnt": min(int(self.config.get("max_count", query.page_size)), 500),
                  "idx": (query.page - 1) * query.page_size + 1}
        terms = query.all_terms()
        if terms:
            params["any"] = " ".join(terms[:1]) if len(terms) == 1 else terms[0]
        if query.title:
            params["title"] = query.title
        if query.creator:
            params["creator"] = query.creator
        if query.subject:
            params["subject"] = query.subject
        if query.date_from:
            params["from"] = str(query.date_from)
        if query.date_to:
            params["until"] = str(query.date_to)
        params.update(self.config.get("extra_params") or {})
        if not any(k in params for k in ("any", "title", "creator", "subject")):
            raise ConnectorError("Requête vide : saisissez au moins un terme.", kind="query", code="empty_query")
        response = ConnectorHTTP(self.catalogue).get(ENDPOINT, params=params, accept="application/rss+xml, application/xml")
        results, total = parse_opensearch(response["text"])
        # Variantes : interrogations complémentaires (limitées, réglables) puis dédoublonnage par identifiant.
        # L'échec d'une variante n'annule pas les résultats déjà obtenus : il devient un avertissement.
        seen = {r.source_id for r in results}
        warnings = []
        for variant in terms[1:1 + int(self.config.get("max_variants", 3))]:
            extra = dict(params, any=variant, idx=1)
            try:
                more, _ = parse_opensearch(ConnectorHTTP(self.catalogue).get(
                    ENDPOINT, params=extra, accept="application/rss+xml")["text"])
            except ConnectorError as exc:
                warnings.append(f"Variante « {variant} » non interrogée : {exc}")
                continue
            for r in more:
                if r.source_id not in seen:
                    seen.add(r.source_id)
                    results.append(r)
        return SearchResponse(results=results, total=total, page=query.page,
                              has_more=bool(total and query.page * query.page_size < total), warnings=warnings,
                              elapsed_ms=int((time.monotonic() - started) * 1000))
