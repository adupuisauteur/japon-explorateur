"""
Évaluation des moteurs sur un corpus de référence (plan 1.3.0, lot 10 ; cahier des charges § 15).

- Le corpus est un projet du compte marqué « Corpus de référence » ; il ne doit contenir aucun texte
  confidentiel (fourni ou validé par l'utilisateur). Les tests automatiques n'utilisent que des textes fictifs.
- « Comparer les moteurs » prépare une tâche par moteur (nature « evaluation ») sur tous les segments du
  corpus, sans reprise de la mémoire ni exclusion des segments validés ; RIEN n'est envoyé avant la
  confirmation du coût estimé de chaque moteur. Les résultats sont des versions datées, conservées pour
  des comparaisons ultérieures (Ollama plus tard).
- L'appréciation est HUMAINE : l'utilisateur note chaque traduction (correcte, acceptable, fautive,
  contresens) et peut commenter. Aucun score automatique n'est calculé ni présenté : la page ne montre que
  la répartition des notes données par l'utilisateur.
"""
from collections import Counter, OrderedDict

from django.utils import timezone

from . import services
from .models import RATINGS, TranslationJob
from .segmentation import is_translatable

LABEL_PREFIX = "Comparaison du "


class EvaluationError(Exception):
    pass


def corpus_projects(user):
    return user.translation_projects.filter(is_reference_corpus=True).order_by("title")


def check_corpus(project, user):
    if project.owner_id != user.pk:
        raise EvaluationError("Seul le propriétaire du corpus peut lancer une comparaison.")
    if not project.is_reference_corpus:
        raise EvaluationError("Ce projet n'est pas marqué « Corpus de référence » (modifiez le projet).")


def corpus_segments(project):
    segments = []
    for document in project.documents.order_by("order", "pk"):
        segments += [s for s in document.segments.order_by("position") if is_translatable(s.source_text)]
    return segments


def prepare_comparison(user, project, choices):
    """Prépare une tâche par moteur (aucun envoi). Retourne (libellé, tâches préparées, [(moteur, erreur)])."""
    check_corpus(project, user)
    unique = list(OrderedDict.fromkeys(c for c in choices if c))
    if not unique:
        raise EvaluationError("Choisissez au moins un moteur à comparer.")
    segments = corpus_segments(project)
    if not segments:
        raise EvaluationError("Le corpus ne contient aucun segment à traduire : ajoutez-y un document.")
    label = f"{LABEL_PREFIX}{timezone.localtime():%d/%m/%Y %H:%M:%S} — {project.title}"[:300]
    jobs, errors = [], []
    for choice in unique:
        specs = [{"segment": s, "text": s.source_text} for s in segments]
        try:
            jobs.append(services._prepare(user, "evaluation", specs, project=project, choice=choice,
                                          scope_label=label))
        except services.TranslationUnavailable as exc:
            errors.append((choice, str(exc)))
    return label, jobs, errors


def comparison_jobs(user, project, label):
    return list(TranslationJob.objects.filter(user=user, project=project, kind="evaluation", scope_label=label)
                .order_by("pk"))


def comparisons(user, project):
    """Comparaisons du corpus, de la plus récente à la plus ancienne : [(libellé, [tâches])]."""
    groups = OrderedDict()
    for job in (TranslationJob.objects.filter(user=user, project=project, kind="evaluation")
                .order_by("-created_at", "pk")):
        groups.setdefault(job.scope_label, []).append(job)
    return [(label, sorted(jobs, key=lambda j: j.pk)) for label, jobs in groups.items()]


def rows(jobs):
    """Une ligne par segment : (segment, [version produite par chaque tâche, ou None])."""
    by_job = {}
    order = []
    for job in jobs:
        items = job.items.select_related("segment__document", "version").order_by("position")
        by_job[job.pk] = {i.segment_id: i for i in items}
        if not order:
            order = [i.segment for i in items if i.segment_id]
    return [(segment, [by_job[j.pk].get(segment.pk) for j in jobs]) for segment in order]


def rating_summary(jobs):
    """Répartition des notes HUMAINES par moteur (aucun score calculé)."""
    out = []
    for job in jobs:
        versions = [i.version for i in job.items.select_related("version") if i.version_id]
        counts = Counter(v.rating or "unrated" for v in versions)
        out.append({"job": job, "label": services.engine_label(job), "counts": [(code, label, counts.get(code, 0)) for code, label in RATINGS],
                    "unrated": counts.get("unrated", 0), "total": len(versions)})
    return out


def rate(version, user, rating, comment):
    project = version.segment.document.project
    if project.owner_id != user.pk:
        raise EvaluationError("Seul le propriétaire du corpus note les traductions.")
    if rating not in {code for code, _ in RATINGS} | {""}:
        raise EvaluationError("Appréciation inconnue.")
    version.rating, version.rating_comment = rating, (comment or "").strip()[:2000]
    version.save(update_fields=["rating", "rating_comment"])
    return version


def confirm_all(jobs, user, *, second_confirmation=False, terms_acknowledged=False):
    """Confirme les tâches préparées ; retourne (lancées, [(tâche, erreur)])."""
    started, errors = [], []
    for job in jobs:
        if job.status != "draft":
            continue
        try:
            services.confirm(job, user, second_confirmation=second_confirmation,
                             terms_acknowledged=terms_acknowledged)
            started.append(job)
        except services.TranslationUnavailable as exc:
            errors.append((job, str(exc)))
    return started, errors
