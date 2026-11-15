# J-ed 2.0.0 — Demandes de l'utilisateur en cours de développement

Demandes faites pendant le développement, en plus du cahier des charges. Chacune indique le lot où elle est
traitée et son état.

| N° | Date | Demande | Lot | État |
| --- | --- | --- | --- | --- |
| U1 | 15/11/2026 | Valider et adopter en une fois les traductions de plusieurs champs, au lieu d'un clic par champ | 0 | Fait (archive `lot0e`) : bouton « Tout valider et adopter » sur la fiche, la page « Traductions » et la page de la tâche |
| U2 | 15/11/2026 | Exports de fiches : en bas de page, indiquer la date, l'heure, le nom de l'application et l'utilisateur | 1 | Fait (archive `lot1`) : exports Word, PDF, HTML et texte, et exports des projets de traduction |
| U3 | 15/11/2026 | Lien « À propos » dans le menu du bas de page ; l'entrée du menu utilisateur n'est pas utile | 1 | Fait (archive `lot1b`) : lien « À propos » en bas de page pour tout compte connecté, retiré du menu utilisateur |
| U4 | 15/11/2026 | Historique des versions dans l'Administration : évolutions et améliorations, sans lister les bugs rencontrés | 6 | À faire, avec l'affichage du Markdown de l'aide intégrée |
| U5 | 15/11/2026 | Module de traduction : retrouver les traductions déjà effectuées | 3 | À faire, avec la page « Tâches » |

## U2 — Pied de page des exports

**Aujourd'hui (1.3.0, lot 0)**, le pied de page d'un export Word ou PDF contient le texte libre « Pied de
page », l'identifiant de l'export et le numéro de page. Le site HTML y ajoute le nom et la version de
l'application. La date de production n'apparaît que dans les métadonnées et la page de garde.

**Proposition (lot 1).** Sur chaque page des exports Word, PDF et HTML, le pied de page indiquerait :

- la date et l'heure de production (heure de Paris) ;
- « J-ed » et sa version ;
- le nom affiché de l'utilisateur qui a produit l'export ;
- l'identifiant de l'export et le numéro de page, comme aujourd'hui.

Le texte libre « Pied de page » de l'export reste possible.

**Décisions de l'utilisateur (15 novembre 2026, début du lot 1)** :

- l'**identifiant de connexion** est indiqué, pas le nom affiché ;
- une case **« Ne pas indiquer mon identifiant »** sur l'écran d'export le retire (export destiné à être
  diffusé) ; le choix est conservé quand l'export est régénéré ;
- le **même bas de page** pour les exports des projets de traduction.

**Réalisé** :

- Word et PDF : sur chaque page après la couverture, le texte libre « Pied de page » s'il y en a un, puis
  « Produit le JJ/MM/AAAA à HH:MM · J-ed 2.0.0 · par <identifiant> », l'identifiant de l'export et le numéro
  de page. La couverture indique aussi « Exporté par ».
- Site HTML : la même ligne au bas de chaque page. Texte : en dernière ligne.
- Projets de traduction : bas de page sur chaque page du Word bilingue ; en dernière ligne des exports texte et
  Markdown ; « Exporté par » dans l'en-tête. Le tableau CSV n'a pas de bas de page (fichier de données).
- Heure de Paris (réglage `TZ` de l'installation).

## U4 — Historique des versions dans l'Administration

**Constat.** Le fichier `CHANGELOG.md` est un journal technique : noms de fichiers, migrations, décisions,
corrections. Il n'est pas affiché dans l'application.

**Demande (15 novembre 2026).** Une rubrique de l'Administration présente, version par version, les
**évolutions et améliorations**, sans lister les bugs rencontrés ni leurs corrections.

**Prévu au lot 6** :

- un texte rédigé pour l'utilisateur, distinct du `CHANGELOG.md` technique, tenu à jour à chaque lot ;
- affiché dans l'Administration (« Historique des versions ») ;
- la page « Quoi de neuf » de l'aide intégrée (cahier § 9) reprend la même source pour la dernière version.

## U5 — Retrouver les traductions déjà effectuées

**Aujourd'hui (lot 1)**, elles sont dispersées : Traduction → Tâches (une tâche à la fois), la page
« Traductions » de chaque notice, l'atelier de chaque document de projet, la mémoire de traduction.

**Prévu au lot 3**, avec la page « Tâches » : une vue d'ensemble des notices traduites, avec un filtre par
état (proposée, validée, à revoir parce que l'original a changé), par moteur et par date, et un lien vers chaque
fiche. Le contenu exact sera proposé au début du lot 3.
