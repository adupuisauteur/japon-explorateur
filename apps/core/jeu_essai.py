"""Jeu d'essai (2.0.0, rc1) : données fictives pour essayer J-ed ou une nouvelle version, avec la page d'aide
« Essayer J-ed ».

Tout est inventé (titres, auteurs, fonds, textes) et rangé à part : une source « Jeu d'essai (fictif) » (code
`jeu-essai`), un dossier et un projet de traduction dont le titre commence par « [Essai] ». Le retrait ne supprime que
ces éléments-là ; une notice d'essai encore utilisée ailleurs (tâche de traduction, par exemple) est gardée et
signalée. Aucun appel réseau.
"""
from django.db import transaction
from django.db.models import ProtectedError

CATALOGUE_CODE = "jeu-essai"
MARK = "[Essai]"
FOLDER_TITLE = f"{MARK} Dossier fictif"
PROJECT_TITLE = f"{MARK} Projet de traduction fictif"
RIGHTS = "Notice fictive du jeu d'essai de J-ed : aucune donnée réelle."

AUTHORS = [("架空太郎", "かくう たろう"), ("夢野花子", "ゆめの はなこ"), ("試験一郎", "しけん いちろう"),
           ("藤見次郎", "ふじみ じろう"), ("春野小町", "はるの こまち")]
PLACES = ["架空文庫", "試験図書館", "夢見大学附属図書館"]
KINDS = [("写本", "manuscrit"), ("刊本", "imprimé"), ("版本", "xylographie"), ("巻子本", "rouleau")]
ERAS = ["寛永三年", "元禄十年", "享保五年", "天明二年", "文化八年", "天保十二年", "明治十五年"]
TITLES = [
    ("架空物語集", "かくうものがたりしゅう"), ("夢の浮橋考", "ゆめのうきはしこう"), ("試験和歌抄", "しけんわかしょう"),
    ("春霞日記", "はるがすみにっき"), ("月見草紙", "つきみそうし"), ("架空名所図会", "かくうめいしょずえ"),
    ("夢見百首", "ゆめみひゃくしゅ"), ("試験随筆", "しけんずいひつ"), ("架空旅日記", "かくうたびにっき"),
    ("花鳥架空抄", "かちょうかくうしょう"), ("秋風草子", "あきかぜそうし"), ("架空絵巻", "かくうえまき"),
    ("夢路往来", "ゆめじおうらい"), ("試験軍記", "しけんぐんき"), ("架空俳諧集", "かくうはいかいしゅう"),
    ("雪見紀行", "ゆきみきこう"), ("架空茶話", "かくうちゃわ"), ("夢想歌枕", "むそううたまくら"),
    ("試験漢詩集", "しけんかんししゅう"), ("架空家集", "かくうかしゅう"), ("朧月物語", "おぼろづきものがたり"),
    ("架空名寄", "かくうなよせ"), ("夢見草", "ゆめみぐさ"), ("試験注釈", "しけんちゅうしゃく"),
    ("架空縁起", "かくうえんぎ"), ("春雨草紙", "はるさめそうし"), ("架空狂歌集", "かくうきょうかしゅう"),
    ("夢の通ひ路", "ゆめのかよいじ"), ("試験往来物", "しけんおうらいもの"), ("架空地誌", "かくうちし"),
    ("花筏日記", "はないかだにっき"), ("架空能楽考", "かくうのうがくこう"), ("夢想集", "むそうしゅう"),
    ("試験書簡", "しけんしょかん"), ("架空草双紙", "かくうくさぞうし"), ("星合物語", "ほしあいものがたり"),
]
#: Doublon volontaire : même œuvre, graphie ancienne (國) et moderne (国), même auteur.
DUPLICATES = [("架空國史略", "かくうこくしりゃく"), ("架空国史略", "かくうこくしりゃく")]

MODERN_TEXT = ("これは架空の文章です。山のふもとに小さな図書館があり、古い本がたくさん並んでいました。\n"
               "ある日、若い研究者がその図書館を訪れ、一冊の和本を手に取りました。")
#: Texte en langue classique (bungo) écrit pour le jeu d'essai, sans emprunt à une œuvre réelle.
CLASSICAL_TEXT = ("むかし、架空の里に一人の翁ありけり。朝ごとに川のほとりに出でて、流るる水を眺めけり。\n"
                  "人のいふやう、「何をか見給ふ」と。翁こたへて、「ただ過ぎゆく月日を見るなり」といひけり。")


def _records():
    rows = []
    for n, (title, reading) in enumerate(TITLES, start=1):
        author, author_reading = AUTHORS[n % len(AUTHORS)]
        kind, kind_fr = KINDS[n % len(KINDS)]
        data = {
            "source_id": f"ESSAI-{n:03d}", "original_title": title, "reading": reading,
            "creator_original": author, "creator_reading": author_reading,
            "copy_date_text": ERAS[n % len(ERAS)], "material_type_original": kind,
            "holding_institution_text": PLACES[n % len(PLACES)], "shelfmark": f"架-{n:03d}",
            "subjects_original": ["物語", "和歌", "日記", "随筆", "紀行"][n % 5],
            "description_original": f"{kind_fr.capitalize()} fictif du jeu d'essai, {1 + n % 4} volume(s).",
            "rights_and_access": RIGHTS, "language": "ja",
        }
        if n % 3 == 0:  # une notice sur trois annonce une numérisation (adresse fictive, jamais appelée)
            data["digital_access_url"] = f"https://example.org/jeu-essai/{n:03d}"
            data["digital_access"] = "image"
        rows.append(data)
    for n, (title, reading) in enumerate(DUPLICATES, start=101):
        rows.append({"source_id": f"ESSAI-{n:03d}", "original_title": title, "reading": reading,
                     "creator_original": "試験一郎", "creator_reading": "しけん いちろう", "copy_date_text": "文化八年",
                     "material_type_original": "刊本", "holding_institution_text": PLACES[n % 2],
                     "description_original": "Doublon volontaire du jeu d'essai (même œuvre, autre graphie).",
                     "rights_and_access": RIGHTS, "language": "ja"})
    return rows


def present():
    from apps.catalog.models import Record

    return Record.objects.filter(catalogue__code=CATALOGUE_CODE).count()


def load(user):
    """Charge (ou complète) le jeu d'essai. Idempotent. Retourne un résumé."""
    from apps.catalog.models import Catalogue
    from apps.catalog.services import upsert_record
    from apps.library.models import Collection, CollectionRecord, LibraryEntry
    from apps.translation.models import TranslationProject
    from apps.translation.projects import create_document

    created = 0
    with transaction.atomic():
        catalogue, _ = Catalogue.objects.get_or_create(code=CATALOGUE_CODE, defaults={
            # Pas de connecteur propre : les notices se trouvent par « Base locale », comme une source importée
            # (avec le connecteur « local », elles sortaient deux fois dans une même recherche).
            "name": "Jeu d'essai (fictif)", "name_original": "試験用データ", "status": "available",
            "connector": "", "enabled_for_search": False, "sort_order": 98,
            "role": "Notices inventées pour essayer J-ed : aucune donnée réelle. Retrait : Administration → Jeu "
                    "d'essai.",
            "access_method": "Chargé par J-ed (jeu d'essai) ; aucun appel réseau."})
        records = []
        for data in _records():
            record, status = upsert_record(catalogue, data, origin="import", user=user,
                                           dataset_label="Jeu d'essai J-ed", note="Jeu d'essai (fictif)")
            created += status == "created"
            records.append(record)
        folder, _ = Collection.objects.get_or_create(owner=user, title=FOLDER_TITLE, defaults={
            "description": "Dossier du jeu d'essai : notices fictives."})
        for order, record in enumerate(records[:8]):
            LibraryEntry.objects.get_or_create(user=user, record=record)
            CollectionRecord.objects.get_or_create(collection=folder, record=record,
                                                   defaults={"order": order, "added_by": user})
        project, new_project = TranslationProject.objects.get_or_create(owner=user, title=PROJECT_TITLE, defaults={
            "description": "Projet du jeu d'essai : deux textes inventés, l'un moderne, l'autre en langue classique.",
            "collection": folder})
        if new_project:
            create_document(project, title=f"{MARK} Texte moderne", text=MODERN_TEXT, variety="modern",
                            confidence="sure", record=records[0])
            create_document(project, title=f"{MARK} Texte classique (bungo)", text=CLASSICAL_TEXT,
                            variety="classical", confidence="sure", record=records[1])
    return {"notices": len(records), "créées": created, "dossier": folder.title, "projet": project.title}


def remove():
    """Retire le jeu d'essai, et lui seul. Retourne un résumé ; une notice encore utilisée ailleurs est gardée."""
    from apps.catalog.models import Catalogue, Record
    from apps.library.models import Collection
    from apps.translation.models import TranslationProject

    summary = {"projets": 0, "dossiers": 0, "notices": 0, "gardées": []}
    for project in TranslationProject.objects.filter(title=PROJECT_TITLE):
        try:
            with transaction.atomic():
                project.delete()
            summary["projets"] += 1
        except ProtectedError:
            summary["gardées"].append(f"projet « {project.title} » (encore utilisé par une tâche)")
    summary["dossiers"] = Collection.objects.filter(title=FOLDER_TITLE).delete()[1].get("library.Collection", 0)
    for record in Record.objects.filter(catalogue__code=CATALOGUE_CODE):
        try:
            with transaction.atomic():
                record.delete()
            summary["notices"] += 1
        except ProtectedError:
            summary["gardées"].append(f"notice {record.source_id} (encore utilisée ailleurs)")
    catalogue = Catalogue.objects.filter(code=CATALOGUE_CODE).first()
    if catalogue and not Record.objects.filter(catalogue=catalogue).exists():
        try:
            with transaction.atomic():
                catalogue.delete()
        except ProtectedError:
            summary["gardées"].append("source « Jeu d'essai (fictif) » (encore référencée)")
    return summary
