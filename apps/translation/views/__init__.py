"""Vues du module de traduction. Lot 1 : page d'accueil de la rubrique (les fonctions arrivent par lots)."""
from django.db.models import Count
from django.shortcuts import render

from apps.core.permissions import researcher_required

from ..permissions import projects_metadata_only_for, projects_with_content_for

#: Rubriques ; chaque lot active la sienne (plan de développement 1.3.0). Nom d'URL vide = pas encore livrée.
SECTIONS = [
    ("bi-cpu", "Moteurs", "Choix des moteurs, clés DeepL et Google, moteurs locaux.", 3, "translation:engines"),
    ("bi-folder2", "Projets et documents", "Import, découpage, traduction, versions et validation.", 6,
     "translation:project_list"),
    ("bi-journal-text", "Glossaires", "Terminologie, import et export CSV.", 7, "translation:glossary_list"),
    ("bi-archive", "Mémoire de traduction", "Paires validées, recherche, exclusion.", 7, "translation:memory"),
    ("bi-hourglass-split", "Tâches", "En cours, file de nuit, programmées, pause, reprise, comptes rendus.", 4,
     "translation:job_list"),
    ("bi-check2-square", "Traductions effectuées", "Notices traduites (filtre par état, moteur, date) et "
     "avancement des documents.", 3, "translation:done"),
    ("bi-file-earmark-arrow-down", "Exports", "Texte, CSV, DOCX bilingue.", 8, "translation:exports"),
    ("bi-speedometer2", "Consommation", "Caractères, coûts estimés et plafonds, par moteur et par mois.", 10,
     "translation:usage"),
    ("bi-clipboard-check", "Évaluation", "Corpus de référence, comparaison des moteurs, notation.", 10,
     "translation:evaluation"),
]


@researcher_required
def home(request):
    mine = projects_with_content_for(request.user).filter(owner=request.user).annotate(n_docs=Count("documents"))
    others = (projects_with_content_for(request.user).exclude(owner=request.user)
              .select_related("owner").annotate(n_docs=Count("documents")))
    hidden = projects_metadata_only_for(request.user).select_related("owner").annotate(n_docs=Count("documents"))
    return render(request, "translation/home.html", {
        "mine": mine, "others": others, "hidden": hidden, "sections": SECTIONS,
    })
