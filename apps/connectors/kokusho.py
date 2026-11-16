"""
Connecteur Kokusho Database — 国書データベース (Institut national de littérature japonaise, NIJL).

Méthodes d'accès retenues après étude (aucune API de recherche publique documentée) :
  1. Notice par identifiant : manifeste IIIF officiel publié pour chaque notice
     (https://kokusho.nijl.ac.jp/biblio/{id}/manifest), identifiant également
     accessible par DOI (10.20730/{id}).
  2. Recherche plein texte : via l'API publique de Japan Search, base « nij16 » par défaut (日本古典籍総合目録,
     catalogue du NIJL sans images, instantané de 2021 ; constaté sur le poste le 16/11/2026), ou la base réglée
     dans « japansearch_db ».
  3. Import de fichiers (listes exportées, CSV fournis par l'utilisateur).

Aucune page HTML n'est aspirée. Conditions d'utilisation :
voir https://kokusho.nijl.ac.jp/page/en/about.html et les mentions de chaque notice (à vérifier avant tout téléchargement d'images).
"""
import re
import time

from .base import BaseConnector, ConnectorError, ConnectorResult, SearchResponse
from .http import ConnectorHTTP, format_error
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


DEFAULT_JPS_DB = "nij16"  # 2.0.0 (lot 10) : base Japan Search des notices du NIJL, constatée sur le poste (16/11/2026)


def _fes(item):
    root = item.get(f"{DEFAULT_JPS_DB}-NihuRoot") or {}
    return ((root.get("nihuDC") or {}).get("FesData") or {}) if isinstance(root, dict) else {}


def _values(fes, key):
    value = fes.get(key) or []
    return [str(v).strip() for v in (value if isinstance(value, list) else [value]) if str(v).strip()]


def parse_nij16(item):
    """Notice du 日本古典籍総合目録 (NIJL) telle que Japan Search la diffuse (base nij16, instantané de 2021).

    Catalogue sans images : titre(s), auteur, sujet, date, édition ou copie (刊/写), format, établissement et cote
    tels que saisis dans la description. Identifiant : celui de Japan Search (« nij16-… »), distinct des numéros de
    notices à images du Kokusho tant que leur correspondance n'est pas vérifiée."""
    if not isinstance(item, dict):
        raise ValueError("élément de résultat non structuré")
    common = item.get("common") or {}
    fes = _fes(item)
    titles = _values(fes, "Title-s") or [str(common.get("title") or "")]
    other_titles = [t for t in dict.fromkeys(titles[1:]) if t != titles[0]]
    description = _values(fes, "Description-s")
    publisher = _values(fes, "Publisher-s")
    extra = []
    if other_titles:
        extra.append("Autres titres : " + " ; ".join(other_titles))
    if publisher:
        extra.append("Éditeur : " + " ; ".join(publisher))
    extra += [f"Format : {f}" for f in _values(fes, "Format-s")]
    info_id = (_values(fes, "Identifier-s") or [""])[0]
    source_id = str(item.get("id") or common.get("id") or (f"{DEFAULT_JPS_DB}-{info_id}" if info_id else ""))
    data = {
        "source_id": source_id,
        "source_url": str(common.get("linkUrl") or ""),
        "original_title": titles[0] or "(sans titre)",
        "creator_original": " ; ".join(_values(fes, "Creator-s")),
        "subjects_original": " ; ".join(_values(fes, "Subject-s")),
        "copy_date_text": " ; ".join(_values(fes, "Date-s")),
        "material_type_original": " ; ".join(_values(fes, "Type-s")),
        "description_original": " ; ".join(description + extra),
        "rights_and_access": "Notice du 日本古典籍総合目録 (NIJL), diffusée par Japan Search (instantané de 2021) ; "
                             "pas d'image dans cette base.",
        "digital_access": "record_only",
        "language": "ja",
    }
    if info_id:
        data["shelfmark"] = ""
    return ConnectorResult(source_id=source_id, data=data, raw=item, raw_format="jpsearch-nij16")


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
            raise ConnectorError("Identifiant Kokusho non reconnu (attendu : numéro, DOI 10.20730/… ou URL /biblio/…).",
                                 kind="query", code="bad_identifier")
        manifest = ConnectorHTTP(self.catalogue).get_json(MANIFEST_URL.format(id=kokusho_id))
        if not isinstance(manifest, dict):
            raise format_error("Manifeste IIIF Kokusho inattendu (objet JSON attendu).", str(manifest)[:300],
                               code="unexpected_structure")
        try:
            return parse_manifest(kokusho_id, manifest)
        except (AttributeError, TypeError, KeyError) as exc:
            raise format_error(f"Manifeste IIIF Kokusho illisible ({exc.__class__.__name__}) : "
                               "son format a peut-être changé.", str(manifest)[:300], code="manifest_structure") from exc

    def search(self, query):
        started = time.monotonic()
        direct = extract_kokusho_id(query.text)
        if direct:
            result = self.fetch_record(direct)
            return SearchResponse(results=[result], total=1, elapsed_ms=int((time.monotonic() - started) * 1000))

        http = ConnectorHTTP(self.catalogue)
        # 2.0.0 (lot 10) : sans réglage, la base nij16 (constatée sur le poste) ; l'ancien filtrage approximatif sur
        # les liens kokusho.nijl.ac.jp ne trouvait rien, ces notices n'ayant pas de tels liens dans Japan Search.
        database = self.config.get("japansearch_db") or DEFAULT_JPS_DB
        warnings = []
        payload = jpsearch_query(http, self.config, query, database=database)
        items = payload.get("list") or payload.get("items") or []
        results = []
        for item in items:
            try:
                parsed = (parse_nij16(item) if f"{DEFAULT_JPS_DB}-NihuRoot" in item
                          else parse_item(item, prefer_kokusho_id=True))
            except (ValueError, TypeError, AttributeError) as exc:
                warnings.append(f"Un résultat illisible a été ignoré ({exc}).")
                continue
            if parsed.raw_format == "jpsearch-nij16":
                results.append(parsed)
                continue
            parsed.data.setdefault("image_url", "")
            if re.fullmatch(r"\d{9}", parsed.source_id):
                parsed.data["image_url"] = MANIFEST_URL.format(id=parsed.source_id)
                if "kokusho.nijl.ac.jp" not in parsed.data.get("source_url", ""):
                    parsed.data["source_url"] = BIBLIO_URL.format(id=parsed.source_id)
            results.append(parsed)
        total = payload.get("hit") if isinstance(payload.get("hit"), int) else None
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
            details.update(error_kind=exc.kind, error_code=exc.code)
            messages.append(f"IIIF officiel : échec ({exc}).")
        try:
            from .base import SearchQuery

            database = self.config.get("japansearch_db") or DEFAULT_JPS_DB
            payload = jpsearch_query(ConnectorHTTP(self.catalogue), self.config,
                                     SearchQuery(text="方丈記", page_size=5), database=database)
            hits = payload.get("hit")
            details["japansearch_db"] = database
            messages.append(f"Japan Search (base {database}) : OK, {hits} notice(s) pour 方丈記.")
        except ConnectorError as exc:
            messages.append(f"Japan Search : échec ({exc}). La recherche par identifiant reste possible.")
        return ok, " ".join(messages), details
