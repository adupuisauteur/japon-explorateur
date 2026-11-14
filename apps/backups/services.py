"""
Sauvegarde et restauration (§15).

Une sauvegarde = une archive .tar contenant :
  - la base (pg_dump au format custom si PostgreSQL, sinon export JSON Django compressé) ;
  - les fichiers (imports, archives sources, exports) en tar.gz ;
  - un manifeste avec empreintes SHA-256, versions de schéma et d'application.
Les clés API y figurent uniquement chiffrées ; la clé de chiffrement (variable
d'environnement) n'y figure jamais et doit être conservée séparément.
"""
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core import management
from django.db import connection, transaction
from django.utils import timezone

from .models import BackupJob

EXCLUDED_MODELS = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _dump_database(target_dir, notes):
    db = settings.DATABASES["default"]
    if settings.IS_POSTGRES and shutil.which("pg_dump"):
        out = target_dir / "database.dump"
        env = dict(os.environ, PGPASSWORD=str(db.get("PASSWORD") or ""))
        cmd = ["pg_dump", "-Fc", "-f", str(out), "-h", str(db.get("HOST") or "localhost"),
               "-p", str(db.get("PORT") or 5432), "-U", str(db.get("USER") or "postgres"), str(db["NAME"])]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            return out, "pg_dump"
        notes.append("pg_dump en échec (" + result.stderr.strip()[-300:] + ") : export JSON de secours utilisé.")
        out.unlink(missing_ok=True)
    elif settings.IS_POSTGRES:
        notes.append("pg_dump introuvable : export JSON de secours utilisé.")
    out = target_dir / "database.json.gz"
    buffer = io.StringIO()
    management.call_command("dumpdata", exclude=EXCLUDED_MODELS, natural_foreign=True, indent=None, stdout=buffer)
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        fh.write(buffer.getvalue())
    return out, "dumpdata"


def _archive_files(target_dir):
    media = Path(settings.MEDIA_ROOT)
    out = target_dir / "files.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        if media.exists():
            tar.add(media, arcname="files")
    return out


def create_backup(kind="full", user=None, scheduled=False):
    from apps.core.models import AppSettings

    job = BackupJob.objects.create(kind=kind, triggered_by=user, scheduled=scheduled)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            parts, method, notes = [], "", []
            if kind in ("full", "db"):
                db_file, method = _dump_database(tmp, notes)
                parts.append(db_file)
            if kind in ("full", "files"):
                parts.append(_archive_files(tmp))
            manifest = {
                "application": "Japon — Explorateur documentaire",
                "application_version": settings.APP_VERSION,
                "data_schema_version": settings.DATA_SCHEMA_VERSION,
                "created_at": timezone.now().isoformat(),
                "kind": kind,
                "database_method": method,
                "database_vendor": connection.vendor,
                "files": {p.name: {"sha256": _sha256(p), "size": p.stat().st_size} for p in parts},
                "secrets": "Non inclus. Conserver séparément DJANGO_SECRET_KEY et AI_KEYS_ENCRYPTION_KEY.",
            }
            (tmp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            archive = settings.BACKUP_DIR / f"sauvegarde-{stamp}-{kind}.tar"
            with tarfile.open(archive, "w") as tar:
                for p in parts + [tmp / "manifest.json"]:
                    tar.add(p, arcname=p.name)
        job.path = str(archive)
        job.size = archive.stat().st_size
        job.sha256 = _sha256(archive)
        job.method = method
        job.status = "done"
        warning = _external_copy(job, archive)
        job.message = " ".join(["Sauvegarde terminée."] + notes + ([warning] if warning else []))
    except Exception as exc:
        # 2.0.0 : le type d'erreur réel est conservé (jamais masqué) et l'incident est journalisé.
        job.status = "failed"
        job.message = f"Échec : {exc.__class__.__name__} : {exc}"[:2000]
        _record_failure(exc, "Sauvegarde")
    job.finished_at = timezone.now()
    job.save()
    _rotate(AppSettings.get().backup_retention)
    return job


def _external_copy(job, archive):
    """Copie dans BACKUP_EXTERNAL_DIR (dossier visible dans Windows en 2.0.0).

    Un échec de la copie ne rend pas la sauvegarde invalide : l'archive principale est créée et vérifiable.
    Il est signalé dans le message de la sauvegarde et journalisé. Retourne le texte d'avertissement ou "".
    """
    if not settings.BACKUP_EXTERNAL_DIR:
        return ""
    try:
        ext = Path(settings.BACKUP_EXTERNAL_DIR)
        ext.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, ext / archive.name)
        if _sha256(ext / archive.name) != job.sha256:
            raise OSError("empreinte de la copie différente de celle de l'archive")
        job.external_copy = str(ext / archive.name)
        return ""
    except Exception as exc:  # noqa: BLE001 — signalé, jamais masqué
        _record_failure(exc, "Copie externe d'une sauvegarde", severity="warning")
        return f"Attention : copie externe impossible ({exc.__class__.__name__} : {exc})."[:1000]


def _record_failure(exc, operation, severity="error"):
    from apps.incidents.services import record_exception

    record_exception(exc, module="application", operation=operation, severity=severity)


def _rotate(keep):
    done = list(BackupJob.objects.filter(status="done").order_by("-created_at"))
    for old in done[keep:]:
        try:
            if old.path and os.path.exists(old.path):
                os.remove(old.path)
        except OSError:
            continue
        old.delete()


def verify_backup(job):
    """Vérifie l'intégrité : empreinte de l'archive et des éléments, lisibilité du manifeste."""
    problems = []
    if not job.path or not os.path.exists(job.path):
        return False, "Archive introuvable."
    if _sha256(job.path) != job.sha256:
        problems.append("empreinte de l'archive différente")
    with tarfile.open(job.path) as tar, tempfile.TemporaryDirectory() as tmp:
        tar.extractall(tmp, filter="data")
        manifest = json.loads(Path(tmp, "manifest.json").read_text(encoding="utf-8"))
        for name, meta in manifest["files"].items():
            if _sha256(Path(tmp, name)) != meta["sha256"]:
                problems.append(f"empreinte différente pour {name}")
        if "database.json.gz" in manifest["files"]:
            with gzip.open(Path(tmp, "database.json.gz"), "rt", encoding="utf-8") as fh:
                json.load(fh)
        if "files.tar.gz" in manifest["files"]:
            with tarfile.open(Path(tmp, "files.tar.gz")) as ft:
                ft.getmembers()
    job.verified_at = timezone.now()
    job.save(update_fields=["verified_at"])
    return (not problems), ("Intégrité vérifiée." if not problems else "Problèmes : " + ", ".join(problems))


def _restore_json(archive_dir):
    """Restauration depuis l'export JSON de secours, tout ou rien.

    Le fichier est lu et validé AVANT toute suppression ; la base n'est vidée puis
    rechargée qu'à l'intérieur d'une transaction : en cas d'échec, rien n'est perdu.
    """
    fixture_dir = archive_dir / "chargement"
    fixture_dir.mkdir()
    fixture = fixture_dir / "sauvegarde.json"
    with gzip.open(archive_dir / "database.json.gz", "rb") as src, open(fixture, "wb") as dst:
        shutil.copyfileobj(src, dst)
    with open(fixture, encoding="utf-8") as fh:
        objects = json.load(fh)
    if not isinstance(objects, list) or not objects:
        raise ValueError("Export JSON vide ou illisible : restauration annulée, base inchangée.")
    with transaction.atomic():
        management.call_command("flush", interactive=False, verbosity=0)
        management.call_command("loaddata", str(fixture), verbosity=0)


def _restore_pg(dump):
    db = settings.DATABASES["default"]
    env = dict(os.environ, PGPASSWORD=str(db.get("PASSWORD") or ""))
    # --single-transaction + --exit-on-error : tout ou rien.
    cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--single-transaction", "--exit-on-error",
           "-h", str(db.get("HOST") or "localhost"), "-p", str(db.get("PORT") or 5432),
           "-U", str(db.get("USER") or "postgres"), "-d", str(db["NAME"]), str(dump)]
    connection.close()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError("pg_restore a échoué, base inchangée : " + result.stderr[-1500:])


def restore_backup(path, *, restore_db=True, restore_files=True, stdout=None):
    """Restauration complète. Remplace la base ; restaure les fichiers de la sauvegarde.

    Les fichiers de la sauvegarde sont ajoutés ou remplacent ceux du même nom ; les fichiers créés depuis la
    sauvegarde sont conservés (décision D10 de l'audit 2.0.0). Vérifie l'intégrité de l'archive avant toute modification ; la base est restaurée
    en une seule transaction ; les fichiers ne sont copiés qu'après réussite de la base.
    """
    log = []
    with tarfile.open(path) as tar, tempfile.TemporaryDirectory() as tmp:
        tar.extractall(tmp, filter="data")
        tmp = Path(tmp)
        manifest = json.loads((tmp / "manifest.json").read_text(encoding="utf-8"))
        for name, meta in manifest["files"].items():
            if _sha256(tmp / name) != meta["sha256"]:
                raise ValueError(f"Archive corrompue : {name}")
        if restore_files and (tmp / "files.tar.gz").exists():
            with tarfile.open(tmp / "files.tar.gz") as ft:  # extraction préalable : contrôle de lisibilité
                ft.extractall(tmp / "media", filter="data")
        if restore_db:
            if (tmp / "database.dump").exists():
                _restore_pg(tmp / "database.dump")
                log.append("Base restaurée (pg_restore, transaction unique).")
            elif (tmp / "database.json.gz").exists():
                _restore_json(tmp)
                log.append("Base restaurée (export JSON de secours, transaction unique).")
        if restore_files and (tmp / "media" / "files").exists():
            media = Path(settings.MEDIA_ROOT)
            media.mkdir(parents=True, exist_ok=True)
            shutil.copytree(tmp / "media" / "files", media, dirs_exist_ok=True)
            log.append("Fichiers de la sauvegarde restaurés (ajoutés ou remplacés ; les fichiers créés depuis "
                       "la sauvegarde sont conservés).")
    BackupJob.objects.filter(path=str(path)).update(restored_at=timezone.now())
    return log
