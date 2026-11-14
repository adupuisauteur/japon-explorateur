"""
Glossaires du module de traduction (plan 1.3.0, lot 7).

- Saisie et modification des entrées, avec refus des doublons (terme source ou variante déjà présent) ;
  chaque modification incrémente la version du glossaire (Glossary.version).
- Import et export CSV (colonnes ci-dessous ; séparateur virgule, point-virgule ou tabulation détecté ;
  encodage détecté par apps.core.encoding.detect_text).
- Terminologie d'un projet : glossaires du projet par ordre de priorité ; un terme déjà fixé par un
  glossaire plus prioritaire masque le même terme dans les suivants. Les contradictions (même terme,
  traductions différentes) sont listées sans être tranchées automatiquement.
- Application par moteur : DeepL (copie distante envoyée sur action explicite), IA (termes présents
  injectés dans la consigne), Google et Argos (aucune prise en charge : contrôle local seulement).
- Contrôle terminologique local pour tous les moteurs : il SIGNALE (alertes) sans jamais corriger.
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.core.encoding import detect_text

from .memory import normalize
from .models import GLOSSARY_CATEGORIES, Glossary, GlossaryEntry

CSV_COLUMNS = ["source_term", "target_term", "reading", "category", "avoid", "variants", "note", "decision_source"]
#: en-têtes français acceptés à l'import (en plus des noms ci-dessus)
CSV_ALIASES = {
    "terme_source": "source_term", "terme source": "source_term", "original": "source_term",
    "terme_cible": "target_term", "terme cible": "target_term", "traduction": "target_term",
    "lecture": "reading", "categorie": "category", "catégorie": "category",
    "a_eviter": "avoid", "à éviter": "avoid", "a eviter": "avoid",
    "variantes": "variants", "remarque": "note", "source_decision": "decision_source",
    "source de la décision": "decision_source",
}
LIST_SEPARATOR = "|"
MAX_TERM = 300  # longueur des champs du modèle
MAX_IMPORT_BYTES = 2 * 1024 * 1024
CATEGORY_CODES = {code for code, _ in GLOSSARY_CATEGORIES}
CATEGORY_BY_LABEL = {normalize(label).lower(): code for code, label in GLOSSARY_CATEGORIES}
FORMULA_START = ("=", "+", "-", "@")


class GlossaryError(Exception):
    """Saisie ou import refusé ; le message est destiné à l'utilisateur."""


# --------------------------------------------------------------------------- normalisation


def clean_term(value):
    """Supprime tabulations, retours à la ligne et espaces superflus (interdits par DeepL dans un terme)."""
    return re.sub(r"\s+", " ", normalize(value or "")).strip()


def clean_list(values):
    if isinstance(values, str):
        values = values.split(LIST_SEPARATOR)
    out = []
    for v in values or []:
        v = clean_term(v)
        if v and v not in out:
            out.append(v)
    return out


def fold(text):
    """Forme de comparaison : NFKC, minuscules, sans accents ni macrons (ō → o)."""
    decomposed = unicodedata.normalize("NFKD", normalize(text).lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _stem(word):
    """Pluriels simples du français et de l'anglais : « samouraïs » = « samouraï », « shoguns » = « shogun »."""
    if len(word) > 3 and word[-1] in "sx":
        return word[:-1]
    return word


def stems(text):
    return [_stem(w) for w in re.findall(r"\w+", fold(text))]


def _contains_sequence(haystack, needle):
    if not needle:
        return False
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def source_contains(source_text, form, lang):
    """Le terme `form` figure-t-il dans le texte original ? Japonais : sous-chaîne ; anglais : mots entiers."""
    if not form:
        return False
    if lang == "ja":
        return normalize(form) in normalize(source_text)
    return _contains_sequence(stems(source_text), stems(form))


def target_contains(translation, term):
    return _contains_sequence(stems(translation), stems(term))


# --------------------------------------------------------------------------- saisie


def bump(glossary):
    Glossary.objects.filter(pk=glossary.pk).update(version=F("version") + 1)
    glossary.refresh_from_db(fields=["version", "updated_at"])


def _forms_taken(glossary, exclude_entry=None):
    """Formes déjà utilisées dans le glossaire (terme source et variantes) → entrée."""
    taken = {}
    for entry in glossary.entries.exclude(pk=getattr(exclude_entry, "pk", None)):
        for form in [entry.source_term, *entry.variants]:
            taken.setdefault(fold(form), entry)
    return taken


def validate_entry(glossary, data, *, entry=None):
    """Retourne un dictionnaire de champs propres ; lève GlossaryError (doublon, champ vide ou trop long)."""
    source = clean_term(data.get("source_term"))
    target = clean_term(data.get("target_term"))
    if not source or not target:
        raise GlossaryError("Le terme source et le terme cible sont obligatoires.")
    for label, value in (("terme source", source), ("terme cible", target), ("lecture", data.get("reading") or "")):
        if len(value) > MAX_TERM:
            raise GlossaryError(f"Le {label} dépasse {MAX_TERM} caractères.")
    category = (data.get("category") or "other").strip()
    category = category if category in CATEGORY_CODES else CATEGORY_BY_LABEL.get(normalize(category).lower(), "")
    if not category:
        raise GlossaryError(f"Catégorie inconnue : « {data.get('category')} ».")
    variants = [v for v in clean_list(data.get("variants")) if fold(v) != fold(source)]
    avoid = [a for a in clean_list(data.get("avoid")) if fold(a) != fold(target)]
    taken = _forms_taken(glossary, exclude_entry=entry)
    for form in [source, *variants]:
        other = taken.get(fold(form))
        if other is not None:
            raise GlossaryError(f"« {form} » figure déjà dans ce glossaire (entrée « {other.source_term} » → "
                                f"« {other.target_term} »).")
    return {"source_term": source, "target_term": target, "reading": clean_term(data.get("reading")),
            "category": category, "variants": variants, "avoid": avoid,
            "note": (data.get("note") or "").strip(), "decision_source": clean_term(data.get("decision_source"))[:300]}


@transaction.atomic
def save_entry(glossary, data, *, entry=None, bump_version=True):
    fields = validate_entry(glossary, data, entry=entry)
    if entry is None:
        entry = GlossaryEntry(glossary=glossary)
    for name, value in fields.items():
        setattr(entry, name, value)
    try:
        with transaction.atomic():
            entry.save()
    except IntegrityError:
        raise GlossaryError(f"« {fields['source_term']} » figure déjà dans ce glossaire.") from None
    if bump_version:
        bump(glossary)
    return entry


@transaction.atomic
def delete_entry(entry):
    glossary = entry.glossary
    entry.delete()
    bump(glossary)


# --------------------------------------------------------------------------- CSV


def _cell(value):
    """Protection contre l'exécution de formules à l'ouverture dans un tableur."""
    value = value or ""
    return "'" + value if value.startswith(FORMULA_START) else value


protect_cell = _cell


def _uncell(value):
    value = value or ""
    return value[1:] if value.startswith("'") and value[1:2] in FORMULA_START else value


def export_csv(glossary):
    """CSV UTF-8 avec marque BOM (ouverture correcte dans Excel), séparateur virgule."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for e in glossary.entries.order_by("source_term"):
        writer.writerow([_cell(v) for v in (e.source_term, e.target_term, e.reading, e.category,
                                            f" {LIST_SEPARATOR} ".join(e.avoid), f" {LIST_SEPARATOR} ".join(e.variants),
                                            e.note, e.decision_source)])
    return "﻿" + buffer.getvalue()


@dataclass
class ImportReport:
    encoding: str = ""
    encoding_confidence: str = ""
    delimiter: str = ""
    added: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    skipped: list = field(default_factory=list)  # (ligne, terme, raison)
    errors: list = field(default_factory=list)  # (ligne, message)
    saved: bool = False

    @property
    def delimiter_label(self):
        return {",": "virgule", ";": "point-virgule", "\t": "tabulation"}.get(self.delimiter, self.delimiter)


def _header_map(header):
    mapping = {}
    for i, name in enumerate(header):
        key = normalize(name).strip().lower().lstrip("﻿")
        key = CSV_ALIASES.get(key, key)
        if key in CSV_COLUMNS and key not in mapping:
            mapping[key] = i
    if "source_term" not in mapping or "target_term" not in mapping:
        raise GlossaryError("En-tête CSV non reconnu : les colonnes « source_term » et « target_term » (ou "
                            "« terme_source » et « terme_cible ») sont obligatoires.")
    return mapping


def read_csv(raw):
    """Décode et découpe un CSV ; retourne (lignes [(numéro, dict)], encodage, fiabilité, séparateur)."""
    if len(raw) > MAX_IMPORT_BYTES:
        raise GlossaryError(f"Fichier trop volumineux (maximum {MAX_IMPORT_BYTES // 1048576} Mo).")
    decoded = detect_text(raw)
    text = decoded.text.lstrip("﻿")
    if not text.strip():
        raise GlossaryError("Le fichier est vide.")
    first = text.splitlines()[0]
    delimiter = max(("\t", ";", ","), key=first.count) if any(d in first for d in "\t;,") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader)
    mapping = _header_map(header)
    rows = []
    for number, row in enumerate(reader, start=2):
        if not any(c.strip() for c in row):
            continue
        rows.append((number, {k: _uncell(row[i]) if i < len(row) else "" for k, i in mapping.items()}))
    return rows, decoded.encoding, decoded.confidence, delimiter


def import_csv(glossary, raw, *, update_existing=False, dry_run=False):
    """Importe un CSV. `dry_run` : vérification seule (rien n'est enregistré). Retourne un ImportReport.

    Doublons : un terme déjà présent dans le glossaire est ignoré (ou mis à jour si `update_existing`) ;
    un terme répété dans le fichier n'est pris qu'à sa première occurrence.
    """
    rows, encoding, confidence, delimiter = read_csv(raw)
    report = ImportReport(encoding=encoding, encoding_confidence=confidence, delimiter=delimiter)
    seen = {}
    by_key = {fold(e.source_term): e for e in glossary.entries.all()}
    try:
        with transaction.atomic():
            for number, data in rows:
                key = fold(clean_term(data.get("source_term")))
                if key and key in seen:
                    report.skipped.append((number, data.get("source_term"), f"répété dans le fichier (ligne {seen[key]})"))
                    continue
                seen[key] = number
                existing = by_key.get(key) if key else None
                if existing is not None and not update_existing:
                    report.skipped.append((number, existing.source_term, "déjà présent dans le glossaire"))
                    continue
                try:
                    entry = save_entry(glossary, data, entry=existing, bump_version=False)
                except GlossaryError as exc:
                    report.errors.append((number, str(exc)))
                    continue
                by_key[fold(entry.source_term)] = entry
                (report.updated if existing is not None else report.added).append(entry.source_term)
            if report.added or report.updated:
                bump(glossary)
            if dry_run:
                raise _DryRun
    except _DryRun:
        glossary.refresh_from_db(fields=["version"])
        return report
    report.saved = True
    return report


class _DryRun(Exception):
    pass


# --------------------------------------------------------------------------- terminologie d'un projet


@dataclass
class Term:
    source: str
    target: str
    forms: list
    avoid: list
    glossary_id: int
    glossary_name: str
    entry_id: int


def project_glossaries(project):
    """Glossaires du projet par priorité (0 = la plus haute), limités à la paire de langues du projet."""
    links = project.glossary_links.select_related("glossary").order_by("priority", "pk")
    return [link.glossary for link in links
            if (link.glossary.source_lang, link.glossary.target_lang) == (project.source_lang, project.target_lang)]


def project_terms(project):
    """Termes applicables ; une forme déjà fixée par un glossaire plus prioritaire est ignorée ensuite."""
    terms, claimed = [], set()
    for glossary in project_glossaries(project):
        for e in glossary.entries.order_by("source_term"):
            forms = [f for f in [e.source_term, *e.variants] if fold(f) not in claimed]
            if not forms:
                continue
            claimed.update(fold(f) for f in forms)
            terms.append(Term(e.source_term, e.target_term, forms, list(e.avoid), glossary.pk, glossary.name, e.pk))
    return terms


def project_contradictions(project):
    """Même terme source, traductions différentes, dans plusieurs glossaires du projet.

    Retourne [(forme, [(glossaire, terme cible), …])] ; le premier glossaire de la liste l'emporte.
    """
    by_form = {}
    for glossary in project_glossaries(project):
        for e in glossary.entries.all():
            for form in [e.source_term, *e.variants]:
                by_form.setdefault(fold(form), (form, []))[1].append((glossary, e.target_term))
    out = []
    for form, uses in by_form.values():
        if len({fold(t) for _, t in uses}) > 1:
            out.append((form, uses))
    return sorted(out, key=lambda x: x[0])


def terms_in(text, terms, lang):
    """Termes dont une forme figure dans `text` ; chaque terme avec la forme trouvée."""
    found = []
    for term in terms:
        form = next((f for f in term.forms if source_contains(text, f, lang)), None)
        if form is not None:
            found.append((term, form))
    return found


def check_terminology(source, translation, terms, lang):
    """Alertes terminologiques (aucune correction) : terme attendu absent, terme à éviter présent."""
    alerts = []
    for term, form in terms_in(source, terms, lang):
        if not target_contains(translation, term.target):
            alerts.append(f"glossaire : « {form} » devrait être traduit par « {term.target} »")
        for bad in term.avoid:
            if target_contains(translation, bad) and not target_contains(term.target, bad):
                alerts.append(f"glossaire : traduction à éviter « {bad} » pour « {form} » (préférer « {term.target} »)")
    return alerts


# --------------------------------------------------------------------------- application aux moteurs


@dataclass
class GlossaryBundle:
    """Glossaire transmis au moteur pour une tâche.

    `terms` : termes du projet (contrôle local et consignes IA) ; `deepl_glossary_id` : copie distante à
    utiliser (DeepL n'accepte qu'un glossaire par requête) ; `refs` : glossaires enregistrés dans chaque
    version (identifiant, nom, version, application native ou non) ; `notes` : avertissements à joindre
    aux segments qui contiennent un terme.
    """

    terms: list
    lang: str = "ja"
    deepl_glossary_id: str = ""
    refs: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def pairs(self):
        """(forme source, terme cible[, à éviter]) pour les consignes IA."""
        return [(form, term.target, term.avoid) for term in self.terms for form in term.forms]

    def found_in(self, text):
        return terms_in(text, self.terms, self.lang)

    def check(self, source, translation):
        return check_terminology(source, translation, self.terms, self.lang)

    def __bool__(self):
        return bool(self.terms)


def remote_copy(glossary, user):
    return (glossary.remote_copies or {}).get(str(user.pk))


def remote_copy_is_current(glossary, user, plan=None):
    """Copie distante utilisable : même version que le glossaire et même offre DeepL que l'envoi."""
    copy = remote_copy(glossary, user)
    if not (copy and copy.get("glossary_id") and copy.get("version") == glossary.version):
        return False
    return plan is None or copy.get("plan") == plan


def bundle_for(project, user, engine_code):
    """Prépare le glossaire d'une tâche ; None si le projet n'a aucun terme."""
    if project is None:
        return None
    glossaries = project_glossaries(project)
    terms = project_terms(project)
    if not terms:
        return None
    bundle = GlossaryBundle(terms=terms, lang=project.source_lang)
    native_id = None
    if engine_code == "deepl":
        from .models import EngineSetting

        setting = EngineSetting.objects.filter(user=user, engine="deepl").first()
        plan = setting.plan if setting else None
        for g in glossaries:
            if remote_copy_is_current(g, user, plan):
                native_id = g.pk
                bundle.deepl_glossary_id = remote_copy(g, user)["glossary_id"]
                break
        if native_id is None:
            if any(remote_copy(g, user) for g in glossaries):
                bundle.notes.append("copie DeepL du glossaire périmée (glossaire modifié ou offre DeepL changée "
                                    "depuis l'envoi) : seul le contrôle local s'applique")
            else:
                bundle.notes.append("glossaire non envoyé à DeepL : seul le contrôle local s'applique")
        elif len(glossaries) > 1:
            bundle.notes.append("DeepL n'applique qu'un glossaire par requête : les autres glossaires du projet "
                                "font l'objet du contrôle local seulement")
    elif engine_code in ("google_basic", "argos"):
        bundle.notes.append("moteur sans glossaire : seul le contrôle local s'applique")
    for g in glossaries:
        bundle.refs.append({"id": g.pk, "name": g.name, "version": g.version,
                            "application": ("native" if g.pk == native_id else
                                            "consigne" if engine_code == "ai" else "controle")})
    return bundle


# --------------------------------------------------------------------------- envoi à DeepL


def deepl_entries(glossary):
    """Entrées TSV pour DeepL : terme source et variantes → terme cible (termes à éviter non envoyés)."""
    lines, seen = [], set()
    for e in glossary.entries.order_by("source_term"):
        for form in [e.source_term, *e.variants]:
            key = fold(form)
            if key in seen or not form or not e.target_term:
                continue
            if len(form.encode()) > 1024 or len(e.target_term.encode()) > 1024:
                continue
            seen.add(key)
            lines.append(f"{form}\t{e.target_term}")
    return lines


def send_problem(glossary, user):
    """Raison de refuser l'envoi à DeepL ('' si l'envoi est possible)."""
    if glossary.owner_id != user.pk:
        return "Seul le propriétaire du glossaire peut l'envoyer à DeepL (avec sa propre clé)."
    if glossary.projects.filter(confidential=True).exists():
        return "Ce glossaire est utilisé par un projet confidentiel : il ne peut pas être envoyé à un service en ligne."
    if not glossary.entries.exists():
        return "Le glossaire est vide."
    return ""


def send_to_deepl(glossary, user):
    """Envoie (ou renvoie) le glossaire à DeepL avec la clé de `user`. Action explicite uniquement.

    Une copie précédente est supprimée après la création de la nouvelle (jamais avant : en cas d'échec,
    l'ancienne reste utilisable ou signalée périmée). Retourne le message à afficher.
    """
    from django.utils import timezone

    from .engines.base import TranslationEngineError
    from .engines.registry import get_engine
    from .journal import record_translation_error

    problem = send_problem(glossary, user)
    if problem:
        raise GlossaryError(problem)
    lines = deepl_entries(glossary)
    if not lines:
        raise GlossaryError("Aucune entrée transmissible à DeepL (termes vides ou trop longs).")
    engine = get_engine("deepl", user)
    try:
        if not engine.glossary_pair_supported(glossary.source_lang, glossary.target_lang):
            raise GlossaryError(f"DeepL n'accepte pas de glossaire {glossary.get_source_lang_display()} → "
                                f"{glossary.get_target_lang_display()} pour ce compte.")
        glossary_id, count = engine.create_glossary(f"{glossary.name} (v{glossary.version})", glossary.source_lang,
                                                    glossary.target_lang, lines)
    except TranslationEngineError as exc:
        record_translation_error(exc, engine="deepl", operation=f"Envoi du glossaire n° {glossary.pk} à DeepL")
        raise
    previous = remote_copy(glossary, user)
    copies = dict(glossary.remote_copies or {})
    copies[str(user.pk)] = {"glossary_id": glossary_id, "version": glossary.version, "entries": count or len(lines),
                            "plan": engine.setting.plan, "sent_at": timezone.now().isoformat()}
    Glossary.objects.filter(pk=glossary.pk).update(remote_copies=copies)
    glossary.remote_copies = copies
    message = f"Glossaire envoyé à DeepL ({count or len(lines)} entrée(s), version {glossary.version})."
    if previous and previous.get("glossary_id") and previous["glossary_id"] != glossary_id:
        try:
            engine.delete_glossary(previous["glossary_id"])
            message += " L'ancienne copie DeepL a été supprimée."
        except TranslationEngineError as exc:  # signalé, jamais masqué
            record_translation_error(exc, engine="deepl",
                                     operation=f"Suppression de l'ancienne copie du glossaire n° {glossary.pk}")
            message += (f" Attention : l'ancienne copie DeepL ({previous['glossary_id']}) n'a pas pu être supprimée "
                        f"({exc}) ; supprimez-la depuis votre compte DeepL.")
    return message


def delete_remote(glossary, user):
    """Supprime la copie DeepL de `user`. Retourne le message à afficher ; la référence locale est retirée."""
    from .engines.base import TranslationEngineError
    from .engines.registry import get_engine
    from .journal import record_translation_error

    copy = remote_copy(glossary, user)
    if not copy:
        raise GlossaryError("Aucune copie DeepL de ce glossaire n'est enregistrée pour votre compte.")
    engine = get_engine("deepl", user)
    try:
        existed = engine.delete_glossary(copy["glossary_id"])
    except TranslationEngineError as exc:
        record_translation_error(exc, engine="deepl", operation=f"Suppression de la copie DeepL du glossaire n° {glossary.pk}")
        raise
    copies = dict(glossary.remote_copies or {})
    copies.pop(str(user.pk), None)
    Glossary.objects.filter(pk=glossary.pk).update(remote_copies=copies)
    glossary.remote_copies = copies
    if existed:
        return "Copie DeepL supprimée."
    return "DeepL ne connaissait plus cette copie (déjà supprimée) : la référence locale a été retirée."
