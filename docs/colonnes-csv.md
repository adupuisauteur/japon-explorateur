# Colonnes des exports CSV

Séparateur interne des valeurs multiples : « ; ». Dates de collecte en ISO 8601, années en entiers.

| Colonne | Type | Définition |
|---|---|---|
| record_id | texte | Identifiant interne stable de la notice (REC-…). |
| catalogue_code | texte | Code technique du catalogue source. |
| catalogue_name | texte | Nom du catalogue source. |
| record_version | entier | Version de la notice exportée. |
| record_status | valeur contrôlée | active, unavailable, withdrawn, to_check. |
| source_id | texte | Identifiant attribué par le catalogue source. |
| source_url | URL | URL officielle de la notice, telle que fournie ou vérifiée. |
| original_title | texte | Titre tel qu'affiché par la source (graphie conservée). |
| reading | texte | Lecture ou transcription fournie par la source. |
| translated_title | texte | Titre traduit ; origine indiquée dans translated_title_origin. |
| translated_title_origin | valeur contrôlée | source, rule, user, ai. |
| creator_original | texte | Auteur, compilateur ou éditeur (forme originale). |
| creator_reading | texte | Lecture du nom de l'auteur. |
| description_original | texte | Description ou 解題 originale. |
| description_translation | texte | Traduction de la description. |
| composition_date_text | texte | Date de composition de l'œuvre telle que fournie. |
| composition_year_start | entier | Année de début (normalisée). |
| composition_year_end | entier | Année de fin (normalisée). |
| composition_date_precision | valeur contrôlée | exact, year, interval, century, period, estimated, unknown. |
| copy_date_text | texte | Date de copie, d'impression ou d'édition de l'exemplaire décrit. |
| copy_year_start | entier | Année de début (normalisée). |
| copy_year_end | entier | Année de fin (normalisée). |
| copy_date_precision | valeur contrôlée | Voir composition_date_precision. |
| document_type_original | texte | Type documentaire fourni par la source. |
| material_type_original | texte | Support fourni par la source. |
| document_type | valeur contrôlée | Type normalisé : chronique, journal, genealogie, registre, traite_militaire, traite, recit, recueil, carte, lettre, poesie, religieux, dictionnaire, autre |
| material_type | valeur contrôlée | Support normalisé : manuscrit, imprime, copie, edition_moderne, transcription, numerique, autre |
| period | valeur contrôlée | Période : nara, heian, kamakura, nanbokucho, muromachi, sengoku, azuchi_momoyama, edo, meiji |
| holding_institution_text | texte | Institution détentrice. |
| shelfmark | texte | Cote. |
| digital_access_url | URL | Lien vers la numérisation. |
| image_url | URL | Manifeste IIIF ou image. |
| digital_access | valeur contrôlée | fulltext, image, record_only, restricted. |
| rights_and_access | texte | Conditions de consultation et de réutilisation connues. |
| language | valeur contrôlée | ja, lzh, fr, en, other. |
| subjects_original | texte | Sujets fournis par la source (séparateur « ; »). |
| place_original | texte | Lieu fourni par la source. |
| source_updated_at | texte | Date de mise à jour indiquée par la source. |
| title_romaji | texte | Rōmaji automatique (lecture non vérifiée). |
| collected_at | date ISO 8601 | Date et heure de collecte. |
| dataset_label | texte | Jeu de données d'origine (import). |

## Profils

- **bibliography** : record_id, catalogue_code, source_id, original_title, reading, translated_title, creator_original, composition_date_text, copy_date_text, holding_institution_text, shelfmark, source_url, collected_at
- **historical** : record_id, original_title, reading, translated_title, creator_original, period, composition_date_text, composition_year_start, composition_year_end, composition_date_precision, copy_date_text, copy_year_start, copy_year_end, copy_date_precision, document_type, material_type, place_original, holding_institution_text, source_url
- **generic** : record_id, catalogue_code, record_version, source_id, source_url, original_title, reading, translated_title, creator_original, creator_reading, description_original, description_translation, composition_date_text, composition_year_start, composition_year_end, composition_date_precision, copy_date_text, copy_year_start, copy_year_end, copy_date_precision, document_type_original, material_type_original, holding_institution_text, shelfmark, digital_access_url, digital_access, rights_and_access, language, subjects_original, place_original, source_updated_at, image_url, collected_at
- **inventory** : record_id, catalogue_code, catalogue_name, record_version, record_status, source_id, source_url, original_title, reading, translated_title, creator_original, creator_reading, description_original, description_translation, composition_date_text, composition_year_start, composition_year_end, composition_date_precision, copy_date_text, copy_year_start, copy_year_end, copy_date_precision, document_type_original, material_type_original, holding_institution_text, shelfmark, digital_access_url, digital_access, rights_and_access, language, subjects_original, place_original, source_updated_at, image_url, period, document_type, material_type, title_romaji, translated_title_origin, collected_at, dataset_label
