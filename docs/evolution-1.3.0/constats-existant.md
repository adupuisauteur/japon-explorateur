# Évolution 1.3.0 — Constats sur l'existant (non corrigés)

Défauts ou limites de la 1.2.0 relevés pendant le développement de la 1.3.0. Ils ne sont **pas corrigés**,
car leur correction sort du périmètre du module de traduction. Chacun pourra faire l'objet d'une décision.

| N° | Constat | Où | Effet | Lot de découverte |
|---|---|---|---|---|
| X1 | Un fichier CSV ou TSV encodé en **EUC-JP** est décodé en cp932, car `decode_text` essaie cp932 avant EUC-JP et qu'un texte EUC-JP « passe » aussi en cp932 | Import (`apps/updates/importers.py`, fonction déplacée sans changement dans `apps/core/encoding.py`) | Texte importé illisible, **sans message** | 2 |
| X2 | Dernier recours de `decode_text` : décodage en latin-1, toujours possible | Même fonction | Texte illisible sans avertissement si aucun encodage ne convient | 2 |

Le module de traduction n'utilise pas `decode_text` mais `detect_text` (même fichier), qui départage
cp932, EUC-JP et UTF-16 par la vraisemblance du texte obtenu et renvoie un indice de fiabilité
(« certaine », « probable », « incertaine »). Une correction de l'import pourrait réutiliser `detect_text`.
