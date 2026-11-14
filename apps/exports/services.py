"""Génération des exports et historique."""
import logging
import mimetypes
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .document import build_document, fingerprint
from .generators.common import sha256_file
from .generators.docx_gen import generate_docx
from .generators.html_site import generate_html, generate_zip
from .generators.pdf_gen import generate_pdf
from .generators.text import generate_csv, generate_json, generate_txt
from .models import ExportFile, ExportJob

logger = logging.getLogger(__name__)

GENERATORS = {
    "docx": generate_docx,
    "pdf": generate_pdf,
    "txt": generate_txt,
    "json": generate_json,
    "csv": generate_csv,
    "html": generate_html,
    "zip": generate_zip,
}

PRESET_DEFAULTS = {
    "bibliography": {"format": "docx", "column_profile": "bibliography", "include_notes": False},
    "inventory": {"format": "csv", "column_profile": "inventory"},
    "dossier": {"format": "docx", "column_profile": "historical", "include_notes": True},
    "synthesis": {"format": "pdf", "include_notes": True},
    "import": {"format": "json", "column_profile": "generic", "include_notes": False},
    "html_doc": {"format": "html", "include_notes": True},
}


def export_dir():
    path = Path(settings.MEDIA_ROOT) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _basename(job):
    slug = re.sub(r"[^\w\-]+", "-", job.title, flags=re.UNICODE).strip("-")[:60] or "export"
    return f"{slug}-{timezone.localtime(job.generated_at):%Y%m%d-%H%M}"


def generate(job):
    job.status = "running"
    job.generated_at = timezone.now()
    job.save(update_fields=["status", "generated_at"])
    try:
        doc = build_document(job)
        target = export_dir() / job.export_uid
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as tmp:
            produced = GENERATORS[job.format](doc, tmp, _basename(job))
            job.files.all().delete()
            for role, path in produced:
                dest = target / Path(path).name
                shutil.move(str(path), dest)
                ExportFile.objects.create(job=job, role=role, path=str(dest.relative_to(settings.MEDIA_ROOT)),
                                          name=dest.name, size=dest.stat().st_size, sha256=sha256_file(dest),
                                          mime_type=mimetypes.guess_type(dest.name)[0] or "application/octet-stream")
        job.metadata = {**doc.metadata, "warnings": doc.options.pop("_warnings", [])}
        job.data_fingerprint = fingerprint(job)
        job.status = "done"
        job.error = ""
    except Exception as exc:
        logger.exception("Export %s en échec", job.export_uid)
        job.status = "failed"
        job.error = f"{exc.__class__.__name__} : {exc}"
    job.save()
    return job


def data_changed_since(job):
    if not job.data_fingerprint:
        return None
    try:
        return fingerprint(job) != job.data_fingerprint
    except Exception as exc:  # 2.0.0 : prudence (« données modifiées ») mais l'erreur est journalisée
        logger.warning("Empreinte de l'export %s incalculable (%s : %s) : données considérées comme modifiées.",
                       job.export_uid, exc.__class__.__name__, exc)
        return True


def clone_for_regeneration(job):
    new = ExportJob.objects.create(
        owner=job.owner, profile=job.profile, preset=job.preset, format=job.format, scope=job.scope,
        scope_params=job.scope_params, title=job.title, subtitle=job.subtitle, subject=job.subject,
        author=job.author, header_text=job.header_text, footer_text=job.footer_text, options=job.options,
        status="pending", regenerated_from=job,
    )
    return new
