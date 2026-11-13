"""
Connecteur NDL Search (国立国会図書館サーチ) — API OpenSearch officielle.
Documentation : https://ndlsearch.ndl.go.jp/help/api/specifications
Réponse RSS 2.0 enrichie (dc, dcterms, dcndl, openSearch).
"""
import time

from lxml import etree

from .base import BaseConnector, ConnectorError, ConnectorResult, SearchResponse
from .http import ConnectorHTTP
from .registry import register

ENDPOINT = "https://ndlsearch.ndl.go.jp/api/opensearch"
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
    "openSearch": "http://a9.com/-/spec/opensearchrss/1.0/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


def _texts(item, path):
    return [(e.text or "").strip() for e in item.findall(path, NS) if (e.text or "").strip()]


def parse_opensearch(xml_text):
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise ConnectorError("Réponse NDL illisible (XML invalide).") from exc
    channel = root.find("channel")
    if channel is None:
        raise ConnectorError("Réponse NDL inattendue (canal RSS absent).")
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
        data = {
            "source_id": source_id,
            "source_url": link if link.startswith("http") else "",
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
                   "max_count": "Nombre maximal de résultats par page (défaut 20, maximum 500)."}

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
            raise ConnectorError("Requête vide : saisissez au moins un terme.")
        response = ConnectorHTTP(self.catalogue).get(ENDPOINT, params=params, accept="application/rss+xml, application/xml")
        results, total = parse_opensearch(response["text"])
        # Variantes : interrogations complémentaires (limitées) puis dédoublonnage par identifiant.
        seen = {r.source_id for r in results}
        for variant in terms[1:3]:
            extra = dict(params, any=variant, idx=1)
            more, _ = parse_opensearch(ConnectorHTTP(self.catalogue).get(ENDPOINT, params=extra,
                                                                         accept="application/rss+xml")["text"])
            for r in more:
                if r.source_id not in seen:
                    seen.add(r.source_id)
                    results.append(r)
        return SearchResponse(results=results, total=total, page=query.page,
                              has_more=bool(total and query.page * query.page_size < total),
                              elapsed_ms=int((time.monotonic() - started) * 1000))
