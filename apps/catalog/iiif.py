"""Vérification d'un manifeste IIIF (2.0.0, lot 2 ; cahier § 5).

Sur action explicite de l'utilisateur (une notice ou une sélection), J-ed :

1. télécharge le manifeste ;
2. contrôle qu'il suit l'API de présentation IIIF 2.x ou 3.0 ;
3. compte ses vues ;
4. teste l'accès à au moins une image (quelques kilo-octets, rien n'est conservé).

Le statut IIIF devient « vérifié » ou « vérification en échec », avec la raison. La demande est enregistrée
en base (`RecordStatus.check_requested_at`) avant tout appel réseau : si l'application s'arrête, les notices
restantes sont reprises au redémarrage, sans refaire celles déjà traitées. Un délai sépare les requêtes
(respect des sites) et chaque échec est inscrit au journal des dysfonctionnements, sans donnée personnelle.
"""
import json
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.connectors.base import ConnectorError
from apps.connectors.http import ConnectorHTTP

from .models import RecordStatus

logger = logging.getLogger(__name__)

LOCK_KEY = "jed:verification-iiif"
LOCK_SECONDS = 300
CHECKABLE = ("identifie", "verifie", "echec", "absent")


class ManifestError(Exception):
    def __init__(self, message, code="manifeste_non_conforme", category="reponse_illisible"):
        super().__init__(message)
        self.code, self.category = code, category


# --------------------------------------------------------------------------- lecture du manifeste


def _context(data):
    ctx = data.get("@context")
    if isinstance(ctx, list):
        return " ".join(str(c) for c in ctx)
    return str(ctx or "")


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _id(obj):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("id") or obj.get("@id") or ""
    return ""


def _image_from_service(services, version):
    for service in _as_list(services):
        base = _id(service).rstrip("/")
        if base.startswith("http"):
            return f"{base}/full/200,/0/default.jpg"
    return ""


def _first_image_v3(canvas):
    for page in _as_list(canvas.get("items")):
        for annotation in _as_list(page.get("items") if isinstance(page, dict) else None):
            for body in _as_list(annotation.get("body") if isinstance(annotation, dict) else None):
                if isinstance(body, dict):
                    image = _image_from_service(body.get("service"), "3.0") or _id(body)
                    if image:
                        return image
    return ""


def _first_image_v2(canvas):
    if not isinstance(canvas, dict):
        return ""
    for annotation in _as_list(canvas.get("images")):
        resource = annotation.get("resource") if isinstance(annotation, dict) else None
        if isinstance(resource, dict):
            image = _image_from_service(resource.get("service"), "2.x") or _id(resource)
            if image:
                return image
    return ""


def inspect(data):
    """Analyse un manifeste déjà décodé : {"version", "type", "views", "image", "members"}.

    Lève ManifestError si ce n'est pas un manifeste ou une collection IIIF 2.x ou 3.0.
    """
    if not isinstance(data, dict):
        raise ManifestError("Le document n'est pas un objet JSON : ce n'est pas un manifeste IIIF.")
    context, kind = _context(data), data.get("type") or data.get("@type") or ""
    if "presentation/3" in context or kind in ("Manifest", "Collection"):
        version = "3.0"
    elif "presentation/2" in context or kind in ("sc:Manifest", "sc:Collection"):
        version = "2.x"
    else:
        raise ManifestError("Ce document ne suit ni l'API de présentation IIIF 2.x ni la 3.0 "
                            "(contexte et type absents ou inconnus).")
    if kind in ("Collection", "sc:Collection"):
        members = [_id(m) for m in _as_list(data.get("manifests") or data.get("items"))
                   if _id(m).startswith("http")]
        return {"version": version, "type": "collection", "views": 0, "image": "", "members": members}
    if kind not in ("Manifest", "sc:Manifest"):
        raise ManifestError(f"Type IIIF inattendu : « {kind or 'non précisé'} » (Manifest attendu).")
    if version == "3.0":
        canvases = [c for c in _as_list(data.get("items")) if isinstance(c, dict) and c.get("type") == "Canvas"]
        image = _first_image_v3(canvases[0]) if canvases else ""
    else:
        sequences = _as_list(data.get("sequences"))
        canvases = _as_list(sequences[0].get("canvases")) if sequences and isinstance(sequences[0], dict) else []
        image = _first_image_v2(canvases[0]) if canvases else ""
    if not canvases:
        raise ManifestError("Le manifeste ne contient aucune vue.", code="manifeste_vide")
    return {"version": version, "type": "manifest", "views": len(canvases), "image": image, "members": []}


# --------------------------------------------------------------------------- vérification


def _fetch_json(http, url):
    result = http.get(url, accept="application/ld+json, application/json;q=0.9", use_cache=False, retries=1)
    try:
        return json.loads(result["text"])
    except ValueError as exc:
        raise ManifestError("La réponse n'est pas du JSON : ce n'est pas un manifeste IIIF.",
                            code="manifeste_illisible") from exc


def check_manifest(url, catalogue):
    """Télécharge et contrôle un manifeste ; retourne le détail à afficher. Lève ManifestError ou ConnectorError."""
    http = ConnectorHTTP(catalogue)
    info = inspect(_fetch_json(http, url))
    prefix = ""
    if info["type"] == "collection":
        if not info["members"]:
            raise ManifestError("Collection IIIF sans manifeste.", code="manifeste_vide")
        prefix = f"Collection de {len(info['members'])} manifeste(s), le premier contrôlé · "
        info = inspect(_fetch_json(http, info["members"][0]))
        if info["type"] != "manifest":
            raise ManifestError("Le premier élément de la collection n'est pas un manifeste.")
    if not info["image"]:
        raise ManifestError("Aucune adresse d'image dans la première vue du manifeste.", code="image_absente")
    probe = http.probe(info["image"])
    if probe["status"] >= 400:
        raise ManifestError(f"Image de la première vue inaccessible (HTTP {probe['status']}).",
                            code=f"image_http_{probe['status']}", category="indisponibilite")
    if not probe["content_type"].lower().startswith("image/"):
        raise ManifestError(f"La première vue ne renvoie pas une image (type « {probe['content_type'] or '?'} »).",
                            code="image_type")
    return f"{prefix}IIIF {info['version']} · {info['views']} vue(s) · image de la première vue accessible"


def verify(row):
    """Vérifie le manifeste d'un statut IIIF et enregistre le résultat. Retourne True si « vérifié »."""
    record = row.record
    ok, code, category = False, "", ""
    try:
        detail = check_manifest(row.url, record.catalogue)
        ok = True
    except ManifestError as exc:
        detail, code, category = str(exc), exc.code, exc.category
    except ConnectorError as exc:
        detail = f"Manifeste injoignable : {exc}"
        code = exc.code or "connect"
        category = "indisponibilite" if exc.kind == "unavailable" else "erreur_technique"
    ndl = row.url.startswith("https://dl.ndl.go.jp/api/iiif/")
    not_published = ndl and not ok and code == "http_404"
    row.value = "verifie" if ok else ("absent" if not_published else "echec")
    row.origin = "jed"
    row.checked_at = timezone.now()
    if not_published:
        detail = ("La NDL ne publie pas de manifeste pour cette numérisation : elle n'est pas en accès libre sur "
                  "Internet (accès réservé probable : envoi aux bibliothèques ou aux particuliers inscrits, ou "
                  "consultation à la NDL).")
    row.detail = detail[:500]
    row.check_requested_at = None
    row.save(update_fields=["value", "origin", "checked_at", "detail", "check_requested_at", "updated_at"])
    if ndl and (ok or not_published):
        _ndl_document_access(record, row, ok)
    if not ok and not not_published:  # un document réservé n'est pas un dysfonctionnement
        from apps.incidents.services import record_incident

        record_incident(module="metadonnees", category=category, severity="warning",
                        title=f"Vérification IIIF en échec : {record.catalogue.name}", message=detail,
                        source_code=record.catalogue.code, operation="Vérification d'un manifeste IIIF",
                        technical_code=code, context={"notice": record.record_id})
        logger.warning("Vérification IIIF en échec (%s, %s) : %s", record.record_id, code, detail)
    return ok


def _ndl_document_access(record, iiif_row, free):
    """2.0.0 (lot 10, reporté du lot 3) : accès d'un document NDL d'après la vérification de son manifeste.
    Étude du 16/11/2026 : une numérisation en accès libre publie son manifeste (HTTP 200, attribution de la NDL) ;
    les numérisations réservées n'en publient pas (HTTP 404). Le niveau exact de réservation n'y figure pas."""
    url = record.digital_access_url or record.source_url
    if free:
        value, detail = "oui", ("Consultable librement sur Internet : la NDL publie le manifeste et la première image "
                                "(vérifié par J-ed).")
    else:
        value, detail = "non_verifie", ("Pas en accès libre sur Internet d'après la NDL (manifeste non publié) : accès "
                                        "réservé probable. La page du document indique les conditions.")
    RecordStatus.objects.update_or_create(record=record, kind="document", defaults={
        "value": value, "origin": "jed", "url": url[:600], "detail": detail, "checked_at": iiif_row.checked_at})


# --------------------------------------------------------------------------- demandes et file


def request_checks(records, user):
    """Inscrit la vérification des notices qui ont un manifeste connu. Retourne (inscrites, sans manifeste)."""
    from .statuses import refresh

    queued, skipped = 0, 0
    now = timezone.now()
    for record in records:
        refresh(record)  # 2.0.0 (lot 10) : statuts recalculés d'abord (adresse NDL construite, sans réseau)
        row = RecordStatus.objects.filter(record=record, kind="iiif").first()
        if row is None or row.value not in CHECKABLE or not row.url:
            skipped += 1
            continue
        row.check_requested_at, row.check_requested_by = now, user
        row.save(update_fields=["check_requested_at", "check_requested_by", "updated_at"])
        queued += 1
    return queued, skipped


def pending():
    return RecordStatus.objects.filter(kind="iiif", check_requested_at__isnull=False)


def run_pending(*, limit=None, delay=None):
    """Traite les vérifications en attente, une à une, avec un délai entre deux notices.

    Un verrou évite deux traitements simultanés ; il est prolongé à chaque notice et expire seul si le worker
    s'arrête. Retourne le nombre de notices traitées.
    """
    if not cache.add(LOCK_KEY, "1", LOCK_SECONDS):
        return 0
    delay = settings.IIIF_CHECK_DELAY_SECONDS if delay is None else delay
    done = 0
    try:
        while limit is None or done < limit:
            row = pending().select_related("record__catalogue").order_by("check_requested_at", "pk").first()
            if row is None:
                break
            if done and delay:
                time.sleep(delay)
            cache.set(LOCK_KEY, "1", LOCK_SECONDS)
            verify(row)
            done += 1
    finally:
        cache.delete(LOCK_KEY)
    return done


# --------------------------------------------------------------------------- 2.0.0 (lot 10) : visionneuse


def _label(value):
    """Libellé IIIF 2 (chaîne ou liste) ou 3 (dictionnaire de langues)."""
    if isinstance(value, dict):
        for key in ("ja", "none", "en", "fr"):
            if value.get(key):
                return " ".join(str(v) for v in _as_list(value[key]))
        return " ".join(str(v) for vals in value.values() for v in _as_list(vals))
    if isinstance(value, list):
        return " ".join(_label(v) for v in value)
    return str(value or "")


def _image_at(services, fallback, width):
    for service in _as_list(services):
        base = _id(service).rstrip("/")
        if base.startswith("http"):
            return f"{base}/full/{width},/0/default.jpg"
    return fallback if str(fallback).startswith("http") else ""


def views_of(data, width=1600):
    """Toutes les vues d'un manifeste : [{"label", "image", "thumb"}] (images servies par le serveur IIIF)."""
    inspect(data)
    out = []
    if "presentation/3" in _context(data) or data.get("type") == "Manifest":
        for canvas in _as_list(data.get("items")):
            for page in _as_list(canvas.get("items") if isinstance(canvas, dict) else None):
                for annotation in _as_list(page.get("items") if isinstance(page, dict) else None):
                    body = annotation.get("body") if isinstance(annotation, dict) else None
                    for b in _as_list(body):
                        if isinstance(b, dict):
                            image = _image_at(b.get("service"), _id(b), width)
                            if image:
                                out.append({"label": _label(canvas.get("label")), "image": image,
                                            "thumb": _image_at(b.get("service"), _id(b), 160)})
    else:
        for sequence in _as_list(data.get("sequences"))[:1]:
            for canvas in _as_list(sequence.get("canvases") if isinstance(sequence, dict) else None):
                for annotation in _as_list(canvas.get("images") if isinstance(canvas, dict) else None):
                    resource = annotation.get("resource") if isinstance(annotation, dict) else None
                    if isinstance(resource, dict):
                        image = _image_at(resource.get("service"), _id(resource), width)
                        if image:
                            out.append({"label": _label(canvas.get("label")), "image": image,
                                        "thumb": _image_at(resource.get("service"), _id(resource), 160)})
    return out


def rights_of(data):
    """Mentions à afficher avec les images : attribution, licence, droits (texte brut, jamais interprété en HTML)."""
    from django.utils.html import strip_tags

    lines = []
    for key in ("attribution", "requiredStatement", "license", "rights"):
        value = data.get(key)
        if isinstance(value, dict) and "value" in value:  # IIIF 3 requiredStatement
            value = f"{_label(value.get('label'))} : {_label(value.get('value'))}"
        text = strip_tags(_label(value) if not isinstance(value, str) else value).strip()
        if text:
            lines.append(text)
    return lines


def load_manifest(url, catalogue):
    """Manifeste téléchargé sur demande (ouverture de la visionneuse). Une collection : son premier manifeste."""
    http = ConnectorHTTP(catalogue)
    data = _fetch_json(http, url)
    info = inspect(data)
    if info["type"] == "collection":
        if not info["members"]:
            raise ManifestError("Collection IIIF sans manifeste.", code="manifeste_vide")
        data = _fetch_json(http, info["members"][0])
    return data
