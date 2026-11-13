"""
Connecteur Kokusho Database — 国書データベース (Institut national de littérature japonaise, NIJL).

Méthodes d'accès retenues après étude (aucune API de recherche publique documentée) :
  1. Notice par identifiant : manifeste IIIF officiel publié pour chaque notice
     (https://kokusho.nijl.ac.jp/biblio/{id}/manifest), identifiant également
     accessible par DOI (10.20730/{id}).
  2. Recherche plein texte : via l'API publique de Japan Search, où le fonds
     du NIJL est agrégé, filtrée sur la base Kokusho (identifiant de base à
     configurer ; à défaut, filtrage approximatif sur les liens kokusho.nijl.ac.jp).
  3. Import de fichiers (listes exportées, CSV fournis par l'utilisateur).

Aucune page HTML n'est aspirée. Conditions d'utilisation :
voir https://kokusho.nijl.ac.jp/page/en/about.html et les mentions de chaque notice (à vérifier avant tout téléchargement d'images).
"""
import re
import time

from .base import BaseConnector, ConnectorError, ConnectorResult, SearchResponse
from .http import ConnectorHTTP
from .japansearch import jpsearch_query, parse_item
from .registry import register

BIBLIO_URL = "https://kokusho.nijl.ac.jp/biblio/{id}"
MANIFEST_URL = "https://kokusho.nijl.ac.jp/biblio/{id}/manifest"
DOI_URL = "https://doi.org/10.20730/{id}"
SAMPLE_ID = "200015559"  # 歌仙繪 (NIJL), cité dans la brochure officielle du NIJL

_ID_PATTERNS = [
    re.compile(r"kokusho\.nijl\.ac\.jp/biblio/(\d{6,})"),
    re.compile(r"10\.20730/(\d{6,})"),
    re.compile(r"^\s*(\d{9})\s*$"),
]

LABEL_MAP = {
    "original_title": ["書名", "統一書名", "タイトル", "題名", "title"],
    "reading": ["書名よみ", "よみ", "読み", "title reading", "yomi"],
    "creator_original": ["著者", "作者", "編者", "著編者", "author", "creator"],
    "composition_date_text": ["成立年", "成立", "date of composition"],
    "copy_date_text": ["刊写年", "書写年", "刊年", "出版年", "年代", "date"],
    "material_type_original": ["刊写", "写刊", "刊写の別", "形態", "material", "type"],
    "holding_institution_text": ["所蔵", "所蔵者", "所蔵機関", "holding institution", "holder", "attribution"],
    "shelfmark": ["請求記号", "函架番号", "call number", "shelfmark"],
    "subjects_original": ["分類", "主題", "subject", "category"],
    "description_original": ["注記", "解題", "備考", "note", "description"],
    "rights_and_access": ["利用条件", "ライセンス", "license", "rights"],
    "place_original": ["出版地", "書写地", "place"],
}


def extract_kokusho_id(text):
    for pattern in _ID_PATTERNS:
        m = pattern.search(text or "")
        if m:
            return m.group(1)
    return None


def _iiif_text(value):
    """Texte d'une valeur IIIF v2 (chaîne, liste, {@value}) ou v3 ({langue: [..]})."""
    if value is None:
        return ""
    if isinstance(value, str):
        return re.sub(r"<[^>]+>", "", value).strip()
    if isinstance(value, list):
        return " ; ".join(t for t in (_iiif_text(v) for v in value) if t)
    if isinstance(value, dict):
        if "@value" in value:
            return _iiif_text(value["@value"])
        for lang in ("ja", "none", "jpn", "ja-Latn", "en"):
            if lang in value:
                return _iiif_text(value[lang])
        return " ; ".join(_iiif_text(v) for v in value.values())
    return str(value)


def parse_manifest(kokusho_id, manifest):
    """Transforme un manifeste IIIF (v2 ou v3, Manifest ou Collection) en résultat de connecteur."""
    data = {
        "source_id": kokusho_id,
        "source_url": BIBLIO_URL.format(id=kokusho_id),
        "image_url": MANIFEST_URL.format(id=kokusho_id),
        "original_title": _iiif_text(manifest.get("label")),
    }
    for entry in manifest.get("metadata") or []:
        label = _iiif_text(entry.get("label")).lower()
        value = _iiif_text(entry.get("value"))
        if not value:
            continue
        for field, names in LABEL_MAP.items():
            if any(label == n.lower() or label.startswith(n.lower()) for n in names):
                if field == "original_title" and data.get("original_title"):
                    continue
                data[field] = (data[field] + " ; " + value) if data.get(field) else value
                break
    for key in ("attribution", "requiredStatement"):
        if manifest.get(key) and not data.get("holding_institution_text"):
            data["holding_institution_text"] = _iiif_text(
                manifest[key].get("value") if isinstance(manifest[key], dict) and "value" in manifest[key] else manifest[key]
            )
    rights = manifest.get("license") or manifest.get("rights")
    if rights and not data.get("rights_and_access"):
        data["rights_and_access"] = _iiif_text(rights)
    if manifest.get("description") or manifest.get("summary"):
        data.setdefault("description_original", _iiif_text(manifest.get("description") or manifest.get("summary")))
    kind = manifest.get("@type") or manifest.get("type") or ""
    data["digital_access"] = "image" if ("Manifest" in kind or manifest.get("manifests") or manifest.get("items")
                                         or manifest.get("sequences")) else "record_only"
    data["digital_access_url"] = data["source_url"]
    data["language"] = "ja"
    return ConnectorResult(source_id=kokusho_id, data=data, raw=manifest, raw_format="iiif-manifest")


@register
class KokushoConnector(BaseConnector):
    key = "kokusho"
    label = "Kokusho Database (国書データベース)"
    description = "Notices et images de livres anciens japonais (NIJL) : IIIF officiel + recherche via Japan Search."
    supports_fetch = True
    unsupported_fields = ["translated_title", "description_translation", "creator_reading"]
    config_help = {
        "japansearch_db": "Identifiant de la base Kokusho dans Japan Search (détecté par « Tester le connecteur »).",
        "endpoint": "API de recherche transversale de Japan Search (valeur par défaut recommandée).",
        "db_param": "Nom du paramètre de filtre par base (défaut : f-db).",
    }

    def fetch_record(self, source_id):
        kokusho_id = extract_kokusho_id(source_id)
        if not kokusho_id:
            raise ConnectorError("Identifiant Kokusho non reconnu (attendu : numéro, DOI 10.20730/… ou URL /biblio/…).")
        manifest = ConnectorHTTP(self.catalogue).get_json(MANIFEST_URL.format(id=kokusho_id))
        return parse_manifest(kokusho_id, manifest)

    def search(self, query):
        started = time.monotonic()
        direct = extract_kokusho_id(query.text)
        if direct:
            result = self.fetch_record(direct)
            return SearchResponse(results=[result], total=1, elapsed_ms=int((time.monotonic() - started) * 1000))

        http = ConnectorHTTP(self.catalogue)
        database = self.config.get("japansearch_db")
        warnings = []
        if not database:
            warnings.append("Identifiant de base Japan Search non configuré : filtrage approximatif sur les liens "
                            "Kokusho. Lancez « Tester le connecteur » dans Sources pour le détecter.")
            query.page_size = max(query.page_size, 50)
        payload = jpsearch_query(http, self.config, query, database=database)
        items = payload.get("list") or payload.get("items") or []
        results = []
        for item in items:
            parsed = parse_item(item, prefer_kokusho_id=True)
            link = parsed.data.get("source_url", "")
            if not database and "kokusho.nijl.ac.jp" not in link and "10.20730" not in link:
                continue
            parsed.data.setdefault("image_url", "")
            if parsed.source_id.isdigit():
                parsed.data["image_url"] = MANIFEST_URL.format(id=parsed.source_id)
                if not parsed.data.get("source_url"):
                    parsed.data["source_url"] = BIBLIO_URL.format(id=parsed.source_id)
            results.append(parsed)
        total = payload.get("hit") if (database and isinstance(payload.get("hit"), int)) else None
        return SearchResponse(results=results, total=total if total is not None else len(results), page=query.page,
                              has_more=bool(total and query.page * query.page_size < total), warnings=warnings,
                              elapsed_ms=int((time.monotonic() - started) * 1000))

    def test(self):
        details = {}
        messages = []
        ok = True
        try:
            sample = self.fetch_record(SAMPLE_ID)
            messages.append(f"IIIF officiel : OK (notice d'essai « {sample.title} »).")
        except ConnectorError as exc:
            ok = False
            messages.append(f"IIIF officiel : échec ({exc}).")
        try:
            from .base import SearchQuery

            http = ConnectorHTTP(self.catalogue)
            payload = jpsearch_query(http, self.config, SearchQuery(text="方丈記", page_size=50))
            dbs = {}
            for item in payload.get("list") or []:
                link = str((item.get("common") or {}).get("linkUrl") or "")
                if "kokusho.nijl.ac.jp" in link or "10.20730" in link:
                    db = item.get("database") or (item.get("common") or {}).get("database")
                    if db:
                        dbs[str(db)] = dbs.get(str(db), 0) + 1
            if dbs:
                detected = max(dbs, key=dbs.get)
                details["detected_japansearch_db"] = detected
                messages.append(f"Japan Search : OK, base Kokusho détectée « {detected} ».")
            else:
                messages.append("Japan Search : OK, mais aucune notice Kokusho reconnue dans l'échantillon.")
        except ConnectorError as exc:
            messages.append(f"Japan Search : échec ({exc}). La recherche par identifiant reste possible.")
        return ok, " ".join(messages), details
