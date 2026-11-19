# Données FICTIVES créées avec le code de la 1.2.0.
from apps.accounts.models import User
from apps.catalog.models import Catalogue, EditorialContent
from apps.catalog.services import upsert_record
from apps.library.models import Collection
from apps.ai.models import AITask
from apps.incidents.services import record_incident
from apps.core.audit import log_action
admin = User.objects.create_user("admin-fictif", password="motdepasse-fictif-1", role="admin", is_staff=True, is_superuser=True)
res = User.objects.create_user("chercheur-fictif", password="motdepasse-fictif-2", role="researcher")
cat = Catalogue.objects.order_by("pk").first()
recs = []
for i in range(5):
    r, _ = upsert_record(cat, {"source_id": f"FICTIF-{i}", "original_title": f"架空の書 {i}", "description_original": f"架空の解題 {i}。"})
    recs.append(r)
EditorialContent.objects.create(record=recs[0], kind="translation", target_field="original_title", content="Livre fictif", origin="human", author=res)
task = AITask.objects.create(user=res, function="translation", provider="anthropic", model="modele-fictif", status="done", cost_estimate="0.01")
EditorialContent.objects.create(record=recs[1], kind="translation", target_field="original_title", content="Livre fictif (IA)", origin="ai", ai_task=task, author=res)
col = Collection.objects.create(owner=res, title="Dossier fictif")
record_incident(module="recherche", category="indisponible", severity="warning", title="Incident fictif", message="fictif")
log_action(res, "essai.fictif", None, "Action fictive")
print("données fictives 1.2.0 créées")
