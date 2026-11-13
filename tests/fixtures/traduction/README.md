# Réponses enregistrées fictives — moteurs de traduction (1.3.0)

Réponses **fictives**, construites d'après la documentation officielle des services (format), pour tester
les connecteurs sans appel réseau. Aucune n'a été obtenue d'un service réel ; aucun texte réel.

| Fichier | Service | Situation |
|---|---|---|
| `deepl_translate_ok.json` | DeepL `/v2/translate` | Deux traductions |
| `deepl_usage.json` | DeepL `/v2/usage` | Consommation et limite |
| `deepl_error.json` | DeepL | Corps d'erreur (message) |
| `google_translate_ok.json` | Google Basic v2 | Deux traductions |
| `google_error_key.json` | Google Basic v2 | Clé non valide (HTTP 400) |
| `google_error_quota.json` | Google Basic v2 | Quota atteint (HTTP 429) |
| `argos_health.json` | Service Argos (lot 9) | Paquets ja→en et en→fr installés |
| `ai_translation_ok.json` | IA (contenu de la réponse) | JSON conforme aux consignes |
