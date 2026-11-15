"""Trois statuts indépendants par notice (cahier 2.0.0, § 5 ; audit § 5.1 ; décision D5).

- **Notice disponible** : les métadonnées sont consultables en ligne, chez la source.
- **Document consultable** : les images ou le texte sont accessibles en ligne, pour tous.
- **IIIF** : un manifeste IIIF est connu (« identifié »), puis contrôlé par J-ed (« vérifié » ou « en échec »).

Les statuts sont calculés à partir des métadonnées **déjà enregistrées** (champs et données brutes de la
source), **sans appel réseau** et sans modifier la notice. Aucun statut ne se déduit d'un autre : la présence
d'un manifeste IIIF ne rend pas le document « consultable », un lien vers une numérisation non plus (elle
peut être réservée à la consultation sur place). Ce qui ne peut pas être établi reste « non vérifié ».

Les règles sont volontairement prudentes : un « oui » ou un « absent » n'est retenu que si la source le dit.
"""
import re
from dataclasses import dataclass, field

from django.utils import timezone

KINDS = ("notice", "document", "iiif")

#: Ordre de tri (du plus favorable au moins favorable), pour les listes triées par statut.
SORT_ORDER = {
    "notice": ["oui", "non_verifie", "non"],
    "document": ["oui", "non_verifie", "non"],
    "iiif": ["verifie", "identifie", "non_verifie", "echec", "absent"],
}

LABELS = {
    "oui": "oui", "non": "non", "non_verifie": "non vérifié", "absent": "absent", "identifie": "identifié",
    "verifie": "vérifié", "echec": "vérification en échec",
}
KIND_LABELS = {"notice": "Notice", "document": "Document", "iiif": "IIIF"}
ORIGIN_LABELS = {"source": "déclaré par la source", "jed": "vérifié par J-ed", "deduit": "déduit par J-ed"}

# Mentions d'un accès réservé (consultation sur place, réseau de bibliothèques) dans les conditions d'accès.
ON_SITE_MARKERS = re.compile(
    r"館内|閲覧室|図書館送信|送信サービス|来館|要予約|on[- ]site|reading room|in[- ]library|"
    r"sur place|en salle|restricted|accès restreint|réservé",
    re.IGNORECASE,
)
MANIFEST_MARKER = re.compile(r"manifest", re.IGNORECASE)
IMPORT_FORMATS = {"csv", "tsv", "xlsx", "json", "json_export", "xml", "marcxml", "dc"}
KOKUSHO_MANIFEST = re.compile(r"^https://kokusho\.nijl\.ac\.jp/biblio/\d+/manifest$")


@dataclass
class Status:
    value: str = "non_verifie"
    origin: str = ""
    url: str = ""
    detail: str = ""
    checked_at: object = None
    extra: dict = field(default_factory=dict)

    def as_dict(self):
        return {"value": self.value, "origin": self.origin, "url": self.url, "detail": self.detail,
                "checked_at": self.checked_at.isoformat() if self.checked_at else ""}


def _jps_common(raw):
    common = (raw or {}).get("common") or {}
    if isinstance(common, list):
        common = next((c for c in common if isinstance(c, dict)), {})
    return common if isinstance(common, dict) else {}


def _first(value):
    if isinstance(value, list):
        value = next((v for v in value if v), "")
    if isinstance(value, dict):
        value = value.get("@id") or value.get("id") or value.get("value") or ""
    return str(value or "").strip()


def _on_site(record):
    return bool(record.rights_and_access and ON_SITE_MARKERS.search(record.rights_and_access))


def _catalogue(record):
    if not getattr(record, "catalogue_id", None):
        return None
    try:
        return record.catalogue
    except Exception:  # noqa: BLE001 — catalogue absent (notice en cours de construction)
        return None


def _connector(record):
    return getattr(_catalogue(record), "connector", "") or ""


def _is_local(record):
    catalogue = _catalogue(record)
    return catalogue is not None and (catalogue.code == "local" or catalogue.connector == "local")


def _declared_in_import(record):
    """Valeur d'accès numérique fournie telle quelle par le fichier importé (et non complétée par J-ed)."""
    if record.raw_format not in IMPORT_FORMATS or not record.digital_access:
        return False
    raw = record.raw_data if isinstance(record.raw_data, dict) else {}
    return any(str(v).strip() == record.digital_access for v in raw.values())


# --------------------------------------------------------------------------- règles


def notice_status(record):
    when = record.collected_at
    if record.record_status == "withdrawn":
        return Status("non", "jed", record.source_url, "Notice retirée par la source (constaté lors d'une "
                                                         "synchronisation)", when)
    if _is_local(record):
        return Status("non", "", "", "Notice saisie dans J-ed : pas de notice en ligne")
    if record.source_url and record.source_url_verified:
        detail = "Notice publiée par la source"
        if record.record_status == "unavailable":
            return Status("non_verifie", "source", record.source_url,
                          "Source indisponible lors de la dernière synchronisation", when)
        return Status("oui", "source", record.source_url, detail, when)
    if record.source_url:
        return Status("non_verifie", "deduit", record.source_url, "Adresse construite par J-ed", when)
    return Status("non_verifie", "", "", "Aucune adresse de notice fournie")


def document_status(record):
    when = record.collected_at
    raw = record.raw_data if isinstance(record.raw_data, dict) else {}
    if _on_site(record):
        return Status("non", "source", record.digital_access_url or record.source_url,
                      f"Numérisé, consultation réservée d'après la source : {record.rights_and_access[:300]}", when)
    if record.raw_format == "iiif-manifest":  # Kokusho : manifeste officiel de la notice
        has_views = bool(raw.get("items") or raw.get("sequences") or raw.get("manifests"))
        if has_views:
            return Status("oui", "source", record.digital_access_url or record.source_url,
                          "Images publiées par la source (manifeste IIIF officiel)", when)
        return Status("non_verifie", "", "", "Le manifeste de la source ne décrit aucune image")
    if record.raw_format == "jpsearch-json":
        common = _jps_common(raw)
        iiif, contents = _first(common.get("iiifUrl") or common.get("iiifManifestUrl")), _first(common.get("contentsUrl"))
        if contents.startswith("http") or iiif.startswith("http"):
            return Status("oui", "source", contents if contents.startswith("http") else record.source_url,
                          "Contenu numérique publié en ligne d'après Japan Search", when)
        return Status("non_verifie", "", "", "Japan Search ne signale pas de contenu numérique")
    if record.raw_format == "ndl-opensearch" and record.digital_access_url:
        return Status("non_verifie", "source", record.digital_access_url,
                      "Numérisation signalée par la NDL ; accès (Internet, bibliothèques ou sur place) non précisé",
                      when)
    if record.raw_format == "cinii-jsonld" and record.digital_access_url:
        return Status("non_verifie", "source", record.digital_access_url,
                      "Texte intégral signalé par CiNii ; accès libre non garanti", when)
    if _declared_in_import(record):
        value = {"fulltext": "oui", "image": "oui", "record_only": "non", "restricted": "non"}[record.digital_access]
        detail = {"fulltext": "Texte intégral déclaré par le fichier importé",
                  "image": "Images déclarées par le fichier importé",
                  "record_only": "Notice seule d'après le fichier importé",
                  "restricted": "Accès restreint d'après le fichier importé"}[record.digital_access]
        return Status(value, "source", record.digital_access_url, detail, when)
    if record.digital_access_url:
        return Status("non_verifie", "", record.digital_access_url, "Lien vers une numérisation, accès non vérifié")
    if _is_local(record):
        return Status("non_verifie", "", "", "Notice saisie dans J-ed")
    return Status("non_verifie", "", "", "")


def iiif_status(record):
    when = record.collected_at
    raw = record.raw_data if isinstance(record.raw_data, dict) else {}
    image_url = record.image_url or ""
    if record.raw_format == "iiif-manifest" and image_url:
        return Status("identifie", "source", image_url, "Manifeste officiel publié par la source", when)
    if record.raw_format == "jpsearch-json":
        common = _jps_common(raw)
        declared = _first(common.get("iiifUrl") or common.get("iiifManifestUrl"))
        if declared.startswith("http"):
            return Status("identifie", "source", declared, "Manifeste indiqué par Japan Search", when)
        if KOKUSHO_MANIFEST.match(image_url):  # décision D5 : adresse construite à partir de l'identifiant
            return Status("identifie", "deduit", image_url, "Adresse du manifeste Kokusho construite par J-ed", when)
        return Status("absent", "source", "", "Japan Search n'indique pas de manifeste", when)
    if record.raw_format == "ndl-opensearch":
        if image_url:
            return Status("identifie", "source", image_url, "Manifeste indiqué par la NDL", when)
        if record.digital_access_url:
            return Status("non_verifie", "", "", "Numérisation signalée, manifeste non indiqué par la NDL")
        return Status("absent", "source", "", "La NDL n'indique ni numérisation ni manifeste", when)
    if KOKUSHO_MANIFEST.match(image_url):
        return Status("identifie", "deduit", image_url, "Adresse du manifeste Kokusho construite par J-ed", when)
    if image_url and MANIFEST_MARKER.search(image_url):
        return Status("identifie", "source", image_url, "Adresse de manifeste fournie par la source", when)
    return Status("non_verifie", "", "", "")


RULES = {"notice": notice_status, "document": document_status, "iiif": iiif_status}


def derive(record):
    """Statuts calculés à partir des métadonnées enregistrées : {kind: Status}. Aucun appel réseau."""
    return {kind: RULES[kind](record) for kind in KINDS}


def derive_dict(record):
    """Même calcul, sous forme sérialisable (résultats de recherche non enregistrés)."""
    return {kind: status.as_dict() for kind, status in derive(record).items()}


# --------------------------------------------------------------------------- enregistrement


def refresh(record, *, using=None):
    """Recalcule et enregistre les trois statuts d'une notice enregistrée.

    Une vérification IIIF faite par J-ed (« vérifié » ou « en échec ») est conservée tant que l'adresse du
    manifeste ne change pas. Ne modifie jamais la notice elle-même.
    """
    from .models import RecordStatus

    manager = RecordStatus.objects.db_manager(using) if using else RecordStatus.objects
    existing = {s.kind: s for s in manager.filter(record=record)}
    for kind, status in derive(record).items():
        row = existing.get(kind)
        if row is not None and row.origin == "jed" and kind == "iiif":
            if row.url and row.url == status.url:
                continue
        values = {"value": status.value, "origin": status.origin, "url": status.url[:600],
                  "detail": status.detail[:500], "checked_at": status.checked_at}
        if row is None:
            manager.create(record=record, kind=kind, **values)
        elif any(getattr(row, k) != v for k, v in values.items()):
            if kind == "iiif" and row.url != values["url"]:
                row.check_requested_at = None  # la vérification demandée portait sur l'ancienne adresse
            for k, v in values.items():
                setattr(row, k, v)
            row.save()


def statuses_for(record):
    """Statuts enregistrés d'une notice ({kind: RecordStatus}) ; calculés à la volée s'ils manquent."""
    if record.pk is None:
        return derive(record)
    rows = {s.kind: s for s in record.statuses.all()}
    missing = [k for k in KINDS if k not in rows]
    if missing:
        derived = derive(record)
        for kind in missing:
            rows[kind] = derived[kind]
    return rows


def for_search_result(rec, local=None):
    """Statuts d'un résultat de recherche (sérialisables), calculés depuis les données reçues de la source.

    Si la notice est déjà dans la base et que J-ed y a vérifié le même manifeste IIIF, ce résultat est repris.
    """
    data = derive_dict(rec)
    if local is not None and local.pk:
        row = local.statuses.filter(kind="iiif", origin="jed").first()
        if row is not None and row.url and row.url == data["iiif"]["url"]:
            data["iiif"] = {"value": row.value, "origin": row.origin, "url": row.url, "detail": row.detail,
                            "checked_at": row.checked_at.isoformat() if row.checked_at else ""}
    return data
