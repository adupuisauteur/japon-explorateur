# Évolution 1.2.0 — Étude des accès et priorisation des sources

*Cahier des charges §2.3, §2.4 et §2.8. Étude réalisée le 13 novembre 2026 à partir des documentations officielles. Les serveurs japonais n'étaient pas joignables depuis l'environnement de développement : **aucune source n'a pu être testée en conditions réelles**. Les tests réels se font avec le protocole sous Windows.*

## 1. Mode d'accès réellement disponible, par source

Légende des modes : **API** = interface officielle documentée · **Agrégateur** = accès par l'API d'un agrégateur officiel · **IIIF** = manifestes d'images normalisés · **Import** = fichier fourni par l'institution · **Externe** = consultation sur le site de l'institution uniquement.

| Source | Mode d'accès retenu | Clé | Documentation | Décision 1.2.0 |
|---|---|---|---|---|
| **NDL Search** (国立国会図書館サーチ) | API OpenSearch (RSS + DC-NDL) | Non | ndlsearch.ndl.go.jp/help/api | Conservé, amélioré |
| **NDL Digital Collections** | Liens `rdfs:seeAlso` → dl.ndl.go.jp dans les notices NDL | Non | ndl.go.jp/dlib/standards/lod | Liens repris depuis NDL Search |
| **Japan Search** (ジャパンサーチ) | API web simple (JSON) : items, bases | Non | jpsearch.go.jp/static/developer/webapi | Conservé, corrigé |
| **Archives nationales** (国立公文書館) | Agrégateur : Japan Search, base `najda` (diffusion API « ok » vérifiée dans la liste officielle des bases) | Non | idem | **Nouveau** (source préconfigurée) |
| **CiNii Research** (NII) | API OpenSearch (JSON-LD) | **Oui, gratuite** (`appid`) | support.nii.ac.jp/ja/cir/r_opensearch | **Nouveau connecteur** |
| **Catalogues universitaires** (CiNii Books) | API CiNii Research, type `books` | Oui (même `appid`) | idem | **Nouveau** (source préconfigurée) |
| **Kokusho / NIJL** (国書データベース) | IIIF + Japan Search | Non | kokusho.nijl.ac.jp | Conservé, erreurs mieux classées |
| Archives préfectorales et municipales | Agrégateur Japan Search si l'institution y est connectée et autorise l'API | Non | — | Outil « Trouver une base Japan Search » |
| Waseda (古典籍総合データベース) | Pas d'API de recherche publique identifiée | — | — | Externe, ou Japan Search si la base y est diffusée |
| Kyoto University (貴重資料デジタルアーカイブ) | IIIF par document ; pas d'API de recherche identifiée | — | — | Externe, ou Japan Search si diffusée |
| University of Tokyo HI / SHIPS | Bases en ligne ; aucune API publique documentée identifiée | — | — | Externe |
| Nichibunken (日文研) | Bases en ligne ; à rechercher dans Japan Search | — | — | Outil « Trouver une base Japan Search » |
| CODH | Jeux de données téléchargeables, IIIF | — | codh.rois.ac.jp | Import (existant) |
| Presse ancienne (Kikuzo, Yomidas…) | Services sous abonnement, sans API ouverte | — | — | Externe |
| Aozora Bunko, littérature ancienne | Partiellement présents dans NDL Search et Japan Search | — | — | Via NDL / Japan Search |

Aucune collecte par lecture de pages HTML n'a été mise en place, conformément au §2.4. Une source citée en lien uniquement n'est pas déclarée intégrée.

## 2. Liste courte des connecteurs prioritaires (§2.8)

| Priorité | Connecteur | Intérêt documentaire | Faisabilité / maintenance |
|---|---|---|---|
| 1 | **NDL Search** | Catalogue national le plus large ; liens vers les documents numérisés | API officielle stable, sans clé |
| 2 | **Japan Search** + **bases institutionnelles** (dont Archives nationales) | Un seul accès officiel pour des centaines de bases : archives, universités, musées | API officielle sans clé ; une seule logique à maintenir pour toutes les bases |
| 3 | **CiNii Research** + **CiNii Books** | Revues savantes, thèses, fonds des bibliothèques universitaires | API officielle ; nécessite un identifiant gratuit |
| 4 | **Kokusho** (existant) | Livres anciens et manuscrits, images IIIF | Dépend de Japan Search pour la recherche |

**Raison du choix de Japan Search pour les archives et les universités :** les archives nationales, de nombreuses archives territoriales et des collections universitaires y sont connectées. Japan Search indique pour chaque base si l'institution autorise la diffusion de ses métadonnées par API. Il est préférable de passer par cet accès officiel unique plutôt que d'écrire un connecteur fragile par institution.

## 3. Points à vérifier lors des premiers tests réels

1. **Japan Search** : forme exacte de `common` (objet ou tableau d'objets ; les deux sont acceptés), et acceptation de la période `r-tempo=début,fin` avec une borne vide.
2. **Japan Search** : comportement de la combinaison « OU » (`keyword=+A&keyword=+B`) avec des termes japonais contenant des espaces.
3. **CiNii** : forme des auteurs dans `dc:creator` (chaînes ou objets ; les deux sont acceptés), et code HTTP renvoyé quand l'`appid` est invalide.
4. **NDL** : présence effective du lien `rdfs:seeAlso` vers dl.ndl.go.jp dans les réponses OpenSearch.
5. **Archives nationales** : identifiant de base `najda` toujours valide (relevé dans la liste officielle des bases le 13 novembre 2026).

Chaque écart sera visible dans le journal des dysfonctionnements (« Réponse impossible à interpréter », avec un extrait de la réponse) et pourra être exporté pour correction.
