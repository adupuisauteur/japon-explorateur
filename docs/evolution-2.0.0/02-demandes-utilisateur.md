# J-ed 2.0.0 — Demandes de l'utilisateur en cours de développement

Demandes faites pendant le développement, en plus du cahier des charges. Chacune indique le lot où elle est
traitée et son état.

| N° | Date | Demande | Lot | État |
| --- | --- | --- | --- | --- |
| U1 | 15/11/2026 | Valider et adopter en une fois les traductions de plusieurs champs, au lieu d'un clic par champ | 0 | Fait (archive `lot0e`) : bouton « Tout valider et adopter » sur la fiche, la page « Traductions » et la page de la tâche |
| U2 | 15/11/2026 | Exports de fiches : en bas de page, indiquer la date, l'heure, le nom de l'application et l'utilisateur | 1 | Fait (archive `lot1`) : exports Word, PDF, HTML et texte, et exports des projets de traduction |
| U3 | 15/11/2026 | Lien « À propos » dans le menu du bas de page ; l'entrée du menu utilisateur n'est pas utile | 1 | Fait (archive `lot1b`) : lien « À propos » en bas de page pour tout compte connecté, retiré du menu utilisateur |
| U4 | 15/11/2026 | Historique des versions dans l'Administration : évolutions et améliorations, sans lister les bugs rencontrés | 6 | À faire, avec l'affichage du Markdown de l'aide intégrée |
| U5 | 15/11/2026 | Module de traduction : retrouver les traductions déjà effectuées | 3 | Fait : Traduction → Traductions effectuées |
| U6 | 15/11/2026 | Depuis les résultats, arriver directement sur les documents (pas seulement les notices) ; Aozora Bunko : texte compressé (zip) ou HTML | à placer (lot 10 proposé) | Étude faite, plan à valider |
| U7 | 15/11/2026 | Nouvelles sources : bases du NIJL, 日本古典籍総合目録, Historiographical Institute (東京大学史料編纂所), 日本古典文学大系本文データベース, Waseda Kotenseki | à placer (lot 10 proposé) | Étude faite, plan à valider |
| U8 | 15/11/2026 | IA locale gratuite (comme Argos) pour les résumés | 4 | Fait (lot 4) ; choix du modèle après l'essai réel (V4-6, V4-7) |
| U9 | 15/11/2026 | Résumer directement après la traduction (file d'attente ou de nuit), ou après l'ensemble des traductions | 4 | Fait (lot 4) |
| U10 | 15/11/2026 | Repérer les textes anciens et utiliser une autre IA pour les traduire et les résumer | 4 | Fait (lot 4) ; repérage « testé en simulation », à régler sur tes notices |

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

## U6 et U7 — Documents et nouvelles sources (étude du 15 novembre 2026)

**Demande.** Depuis les résultats de recherche, accéder directement aux documents (images, texte), et pas
seulement aux notices ; pour Aozora Bunko, au texte compressé (zip) ou en HTML. Ajouter les bases du NIJL, le
日本古典籍総合目録, le Historiographical Institute de l'université de Tokyo, le 日本古典文学大系本文データベース
et la base Waseda Kotenseki. Usage visé : retrouver un récit à partir d'une référence indirecte (« existe-t-il
un récit ancien sur telle femme ? »).

**Constats (recherches sur le web, à confirmer sur le poste : l'environnement de développement ne peut pas
joindre ces sites).**

| Source | Constat | Accès envisagé | État dans J-ed |
| --- | --- | --- | --- |
| Aozora Bunko | Œuvres du domaine public, en fichier texte compressé (zip) et en XHTML ; liste de toutes les œuvres en CSV, utilisée par plusieurs projets | Source à part entière depuis la liste CSV (mise à jour périodique), puis texte téléchargé sur demande (zip ou XHTML, ancien encodage, furigana) | Aucun connecteur ; peut-être présent dans NDL Search (non vérifié) |
| 日本古典籍総合目録 | **Fusionné dans le 国書データベース (Kokusho) le 1er mars 2023** ; Kokusho : environ 1,6 million de notices, dont 300 000 avec images (avril 2026), visionneuse IIIF Mirador, DOI pour les notices avec images, notices regroupées par œuvre (著作) | Déjà couvert par le connecteur Kokusho ; à ajouter : regroupement par œuvre, accès direct aux images | Connecteur Kokusho (recherche via Japan Search, manifeste officiel) |
| Autres bases du NIJL | Réorganisation du 1er avril 2023 autour du 国書データベース et du 国文学・アーカイブズ学論文データベース ; les autres bases sont archivées (notices seules) ou fermées | Base des articles (国文学論文) à étudier ; une partie des bases du NIHU est visible dans Japan Search | Via Japan Search, pour ce qui y figure |
| 日本古典文学大系本文データベース | **Publication arrêtée le 31 mars 2023** ; le dépôt du NIJL n'en conserve que la description | Aucun accès possible | — |
| Historiographical Institute (史料編纂所, SHIPS) | 32 bases (catalogues et textes intégraux : 大日本史料総合, 古記録フルテキスト, 古文書フルテキスト) ; images servies en IIIF ; images des originaux et manuscrits du fonds en conditions équivalentes à CC BY | Interface de recherche automatique à étudier (pas d'API publique connue) ; lien direct vers la visionneuse et les images IIIF | Fiche « à étudier » |
| Waseda Kotenseki | Images complètes en accès libre ; une partie en IIIF, avec lien vers le manifeste sur la page de l'ouvrage depuis 2023 ; un lien depuis un site à but scientifique est permis avec mention de la base ; toute réutilisation des images demande une autorisation | Interface de recherche automatique à étudier ; lien direct vers les images, IIIF quand il existe | Fiche « à étudier » |

**Proposition, à valider** : un lot 10, « Documents et nouvelles sources », placé après le lot 3 (tâches),
parce que les téléchargements de textes et les mises à jour de listes passent par la file de tâches.

1. Lien « Ouvrir le document » dans les résultats et les fiches : le meilleur lien vers le document (visionneuse
   de la source, page de lecture), au lieu du manifeste technique.
2. Aozora Bunko : source à part entière, texte téléchargé sur demande, affiché dans J-ed, et envoi possible vers
   un projet de traduction.
3. Kokusho : regroupement des exemplaires d'une même œuvre et accès direct aux images.
4. Waseda Kotenseki et Historiographical Institute : étude de l'accès réel (interface, conditions, fichier
   robots) sur le poste, puis connecteur si c'est permis. Statut « testé en simulation ; test réel à
   confirmer » tant que le test réel n'est pas fait.
5. Visionneuse intégrée des images IIIF (décision de sécurité à prendre : autoriser le chargement d'images de
   sites extérieurs nommés).

## U8, U9, U10 — Lot 4 « Résumés IA, IA locale et textes anciens » (décisions du 15 novembre 2026)

**Résumés (cahier § 7, décision D12).**

- Trois types : résumé court, résumé détaillé, fiche d'analyse (thèmes, personnes, lieux et dates cités).
- Le résumé est toujours rédigé dans la langue de l'utilisateur : français par défaut, autre langue au choix à chaque
  demande.
- Texte lu : l'original japonais par défaut (l'IA rédige directement en français, sans cumuler les erreurs d'une
  traduction automatique). Un résumé fait sur une traduction non validée porte cette mention.
- Exports de notices : case à cocher, décochée par défaut ; mention « généré par IA » toujours présente.

**U9 — Enchaînement avec les traductions.** Au moment de mettre en file : « résumer juste après chaque
traduction » ou « résumer après l'ensemble des traductions ». Le second est imposé la nuit quand Argos et l'IA de
résumé sont tous deux locaux (la mémoire accordée à Docker ne permet pas de les charger ensemble). Le résumé est
une tâche de la file comme les autres : plage de nuit, plafonds, pauses, compte rendu ; son coût est compris dans
l'estimation confirmée.

**U8 — IA locale (Ollama).** Service Docker facultatif et désactivable, comme Argos au lot 7. Aucun modèle n'est
livré ni téléchargé sans confirmation : le bouton d'installation propose deux ou trois modèles qui lisent le
japonais et tiennent dans la mémoire du poste, avec leur taille, puis fait un résumé d'essai. Le choix du modèle
se fait après un essai réel sur le poste de l'utilisateur, y compris sur des textes anciens.

**U10 — Textes anciens.**

1. Repérage automatique proposé (terminaisons classiques, sōrōbun en 候, signes de lecture du kanbun) :
   annotation « japonais ancien probable », que l'utilisateur confirme ou corrige ; jamais présentée comme sûre.
2. Dans Traduction → Moteurs : « Pour le japonais ancien, utiliser… » (traductions et résumés).
3. Une tâche qui mélange textes modernes et anciens est présentée en deux parties à la confirmation, chacune avec
   son moteur et son coût, confirmées en une fois.
4. Jamais de changement de moteur en silence : choix fait d'avance par l'utilisateur et affiché avant l'envoi ;
   plafond atteint = pause, pas d'autre moteur.
5. Statut « testé en simulation » tant que le repérage n'a pas été réglé sur de vraies notices anciennes
   signalées par l'utilisateur.

