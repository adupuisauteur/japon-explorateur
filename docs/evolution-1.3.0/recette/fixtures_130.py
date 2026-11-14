# Usage FICTIF du module 1.3.0 avant le retour (dont une traduction automatique adoptée).
from apps.accounts.models import User
from apps.catalog.models import EditorialContent, Record
from apps.catalog.services import validate_translation
from apps.translation import projects as P, glossary as G
from apps.translation.models import TranslationProject, Glossary, EngineSetting
res = User.objects.get(username="chercheur-fictif"); admin = User.objects.get(username="admin-fictif")
p = TranslationProject.objects.create(owner=res, title="Projet fictif 1.3.0")
d = P.create_document(p, title="Doc", text="架空の文。次の文。")
P.validate_version(P.add_human_version(d.segments.first(), res, "Phrase fictive."), res)
g = Glossary.objects.create(owner=res, name="Glossaire fictif"); G.save_entry(g, {"source_term": "江戸", "target_term": "Edo"})
EngineSetting.objects.create(user=res, engine="argos", enabled=True)
r = Record.objects.filter(source_id="FICTIF-2").first() or Record.objects.order_by("pk")[2]
ed = EditorialContent.objects.create(record=r, kind="translation", target_field="original_title", content="Livre fictif (DeepL)", origin="mt", author=res)
validate_translation(ed, admin)
print("usage fictif 1.3.0 créé")
