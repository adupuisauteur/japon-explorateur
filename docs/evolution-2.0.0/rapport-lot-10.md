# Rapport du lot 10 — documents et nouvelles sources (2.0.0)

*État : lot terminé (étapes 1 à 4, correctif 1), en attente des vérifications V10-1 à V10-11.*

## 1. Périmètre validé (16 novembre 2026)

Proposition U6 et U7 (`02-demandes-utilisateur.md`), acceptée par l'utilisateur, avec deux décisions :
- **Visionneuse : les deux.** Un lien « Ouvrir le document » vers la visionneuse de la source, partout ; une
  visionneuse intégrée à J-ed en option, **désactivée par défaut** dans les Paramètres. La politique de sécurité
  n'est élargie qu'aux sites nommés, et seulement sur la page de la visionneuse.
- **Traduction du japonais ancien en trois étapes : plus tard**, hors du lot 10.

Contenu : lien « Ouvrir le document » ; Aozora Bunko comme source à part entière ; Kokusho (base Japan Search,
regroupement par œuvre, images) ; Waseda Kotenseki, connecteur distinct, avec ses conditions de réutilisation des
images ; vérification d'accès des documents NDL (reportée du lot 3) ; Historiographical Institute (SHIPS) selon ce
qui est permis.

## 2. Faits établis depuis l'environnement de développement (recherches sur le web)

- **Waseda dans NDL Search.** La liste officielle des fonds de l'API NDL Search comprend le
  « 古典籍総合データベース » de la bibliothèque de Waseda (identifiant `waseda`). Recherche et moissonnage sont
  ouverts. La réutilisation des notices est libre à des fins non commerciales et soumise à demande à des fins
  commerciales. Un connecteur Waseda peut donc passer par l'API officielle de NDL Search, sans lire de pages HTML.
- **Aozora Bunko dans NDL Search** : identifiant `aozora`, notices sous licence CC BY.
- **Images de Waseda.** Toute réutilisation des images demande une autorisation. Un site à but scientifique peut
  faire un lien vers les images, à condition d'indiquer qu'il mène au « 早稲田大学図書館古典籍総合データベース ».
  Les images en JPEG et PDF sont utilisables sans démarche pour la recherche. Dans J-ed, ce sera un lien, la
  mention obligatoire et aucun export d'images.
- **Pages d'ouvrage de Waseda** de la forme `https://www.wul.waseda.ac.jp/kotenseki/html/<fonds>/<cote>/index.html`.
  Depuis 2022, elles donnent l'adresse du manifeste IIIF quand il existe.

À confirmer sur le poste : la base Japan Search des notices Kokusho, l'adresse exacte du manifeste Waseda et l'accès
réel des numérisations NDL.

## 3. Étape 1 : commande `etudier_sources`

`docker compose exec web python manage.py etudier_sources`

Lecture seule, une trentaine de requêtes espacées d'une seconde, lancées seulement par l'utilisateur. Rien n'est
enregistré dans la base.

1. Les robots.txt des sites étudiés (Waseda, Aozora, SHIPS, Kokusho, NDL).
2. Japan Search : bases et sites cités dans 100 résultats pour 源氏物語, 歌仙 et 方丈記, avec la structure d'un
   exemple Kokusho. Cela donne la cause de « aucune notice Kokusho reconnue ».
3. Japan Search : les bases dont le nom correspond aux sources étudiées.
4. Kokusho : le manifeste IIIF d'une notice d'essai, et ses champs de droits.
5. NDL Search : les fonds `waseda` et `aozora` (champs et liens de trois notices).
6. Waseda : une seule page d'ouvrage, si robots.txt le permet (liens vers le manifeste, la visionneuse, les PDF et
   les images ; mention des conditions d'utilisation).
7. NDL : pour au plus huit numérisations de la base, le manifeste et le code HTTP d'une vignette de 200 pixels de
   la première vue. Seuls les identifiants de numérisation figurent dans le rapport.
8. Aozora Bunko : les en-têtes de la liste de toutes les œuvres (taille, date), sans la télécharger.
9. SHIPS : formulaires et liens API ou IIIF des pages d'accès aux bases.

Une étape en échec n'arrête pas les autres. Une page que robots.txt n'autorise pas n'est pas lue. Rapport texte,
copié hors du conteneur par `docker compose cp`. Trois tests en simulation.

## 4. Résultats de la première étude (poste de l'utilisateur, 16 novembre 2026, 22 h 05)

| Source | Constat | Conséquence |
| --- | --- | --- |
| Kokusho | Les notices du Kokusho sont dans la base Japan Search `nij16` (« 日本古典籍総合目録 », nom d'avant la fusion de 2023), avec des liens vers `base1.nijl.ac.jp` et non vers `kokusho.nijl.ac.jp`. Des images Kokusho apparaissent aussi par d'autres bases (`THERS_da`), avec l'adresse du manifeste officiel. Le manifeste de la notice d'essai est en IIIF 2, licence « Public Domain Mark », 152 vues. | Cause de « aucune notice Kokusho reconnue » : J-ed cherchait des liens `kokusho.nijl.ac.jp`. Recherche Kokusho à filtrer sur `nij16`, une fois la structure de ses notices connue (second passage). |
| Waseda | NDL Search `dpid=waseda` fonctionne : 223 notices pour 源氏物語, chacune avec l'adresse de sa page Waseda. Le site de Waseda répond 503 (robots.txt et page) et `archive.wul` 403 à une requête automatique. Japan Search en a une partie par la base `arc_books` (portail ARC), avec les adresses de la page de lecture, du PDF et des vignettes. | Connecteur Waseda par NDL Search ; aucune lecture du site de Waseda : liens seulement, avec la mention obligatoire. |
| NDL (numérisations) | Les deux numérisations de la base renvoient 404 au manifeste IIIF. | Probablement des documents à accès réservé, à confirmer par un contrôle positif (second passage). |
| SHIPS | Aucune API ni IIIF repérés ; recherche par un moteur Google intégré. | Pas de connecteur : lien vers le site. |
| Aozora Bunko | robots.txt sans restriction pour J-ed ; liste de 2 Mo, mise à jour le 21 août 2026. Aussi présent dans NDL Search (`aozora`, CC BY) et Japan Search (`aozora`). | Source à part entière (étape 2). |

Défaut de la commande corrigé : un robots.txt en 503 était lu comme « aucune règle », et la page Waseda a été
demandée une fois. Désormais, 401/403 vaut refus total, et 5xx ou site injoignable vaut abstention.

## 5. Étape 2

### 5.1 Aozora Bunko

- **Import.** La liste officielle (CSV compressé, CC BY) est importée par « Synchroniser ». Elle compte une ligne
  par couple (œuvre, personne) ; J-ed les regroupe en une notice par œuvre, avec auteur(s), traducteur(s)
  marqués 訳, texte source (底本), saisie et relecture, et droits (domaine public ou œuvre protégée publiée avec
  accord). Les colonnes sont lues par leur nom. Si une colonne indispensable manque, l'import s'arrête et cite
  les colonnes reçues. La liste du jour est gardée dans un fichier : une reprise ne la télécharge pas de nouveau.
  La synchronisation suit le circuit habituel : rapport à valider, puis intégration.
- **Intégration en tâche de fond.** Mesure ici : 3 000 œuvres en 9 s de préparation et 32 s d'intégration. Les
  17 000 œuvres demanderaient environ 3 minutes, plus que le délai d'une page (180 s). Au-delà de 1 000 notices,
  l'intégration part en tâche de fond. Chaque notice intégrée est marquée, et « Reprendre » continue après une
  interruption.
- **Recherche** dans les notices importées, sans appel au site.
- **Texte intégral.** Il est téléchargé seulement au clic, depuis le fichier zip (Shift_JIS, notation 《》 et ［＃］),
  ou à défaut depuis la page XHTML. Il est gardé tel que reçu dans une nouvelle table `RecordText` (migration
  additive ; un nouveau téléchargement ajoute une ligne et garde l'ancienne). L'affichage montre les furigana
  avec un HTML entièrement échappé : seules les lectures deviennent des balises `<ruby>`. Un caractère hors JIS
  est marqué ※, avec sa description au survol. Le texte source (底本) est repris en bas de page.
- **Vers un projet de traduction** : le texte seul, sans lectures ni notes, est envoyé avec la provenance « Texte
  d'Aozora Bunko » et le lien vers la notice ; la variété (moderne, classique) est suggérée comme pour les autres
  documents.
- Statut : testé en simulation (liste, textes et page XHTML fictifs), test réel à confirmer (V10-3, V10-4).

### 5.2 Registre des connecteurs : cause des tests instables

Le registre ne chargeait les modules des connecteurs que s'il était vide. Or chaque module s'inscrit lui-même
quand on l'importe. Un import isolé, par un test ou par une autre partie de l'application, remplissait donc le
registre à moitié : dans ce processus, NDL, la base locale et les autres sources devenaient « sans connecteur ».
Les nouveaux tests d'Aozora ont rendu l'échec systématique, et le diagnostic ajouté au lot 9 a montré ce message.
Le registre retient désormais qu'il a été chargé, et inscrit lui-même les connecteurs de chaque module. Un test
reproduit la situation. Quatre suites complètes, après redémarrage de PostgreSQL : toutes réussies.

Le même défaut pouvait toucher l'application, si un processus important un connecteur seul avant toute
recherche. Aucun signalement de l'utilisateur ne s'en approche, mais la correction vaut aussi pour lui.

### 5.3 Second passage de l'étude

`etudier_sources` (plan 2) : structure des notices Japan Search des bases `nij16` (Kokusho) et `arc_books`
(Waseda). Pour les numérisations NDL : un contrôle positif (numérisations publiques citées par Japan Search, base
`dignl`) puis celles de la base, par quatre voies (manifeste, API de notice, page, NDL Search). Colonnes exactes de
la liste Aozora. L'ancienne étude reste disponible : `--premiere`.

## 6. Résultats du second passage (16 novembre 2026, 22 h 23)

- **Aozora Bunko** : 19 502 lignes, 55 colonnes, exactement celles qu'attend J-ed.
- **Kokusho, base Japan Search `nij16`** : c'est le 日本古典籍総合目録 du NIJL, figé en septembre 2021, sans
  images. Les notices sont dans un bloc `nij16-NihuRoot.nihuDC.FesData` (Title-s, Creator-s, Subject-s,
  Description-s, Publisher-s, Date-s, Type-s, Format-s, Identifier-s). Le lien mène à la plateforme du NIHU
  (`int.nihu.jp`). 112 notices pour 方丈記, 819 pour 源氏物語.
- **Waseda, base Japan Search `arc_books`** : notices du portail ARC (Ritsumeikan), avec pour fournisseur la
  bibliothèque de Waseda. Elles donnent un manifeste IIIF hébergé par l'ARC (`www.dh-jac.net`), la page de lecture
  et le PDF sur `archive.wul.waseda.ac.jp`, et la mention « Copyright (C) Waseda University Library ». Ce n'est
  qu'une partie du fonds (3 078 réponses pour « 早稲田 源氏 », tous fonds de l'ARC confondus).
- **NDL** : l'étape a dépassé le délai d'attente (25 s) sur une requête, ce qui l'a arrêtée tout entière. Elle
  n'a donc rien conclu.

## 7. Étape 3

- **Kokusho** : sans réglage, la recherche interroge la base `nij16`. Chaque notice garde l'identifiant de Japan
  Search (`nij16-…`), distinct des numéros de notices à images du Kokusho (neuf chiffres) tant que leur
  correspondance n'est pas vérifiée. La recherche par numéro ou DOI (manifeste officiel, images) est inchangée.
  Ces notices sont sans images et figées en 2021 ; leur bandeau « Droits » le dit.
- **Waseda** : nouveau connecteur, branché sur NDL Search (fournisseur `waseda`) et non sur Japan Search
  (`arc_books`), parce que NDL Search couvre tout le catalogue et garantit la réutilisation non commerciale des
  notices. Le lien mène à la page de l'ouvrage, avec la mention exigée. J-ed ne lit jamais le site de Waseda.
  Sur une installation existante, la source « Waseda » garde son réglage : un bandeau explique comment choisir le
  nouveau connecteur. Rien n'est changé d'office. Les manifestes de l'ARC pourraient alimenter la visionneuse
  plus tard. Ils ne le font pas ici, puisque la réutilisation des images demande l'accord de Waseda.
- **« Ouvrir le document »** (fiches et résultats) : le document lui-même plutôt que le manifeste IIIF. Ce peut
  être la visionneuse du Kokusho, la page NDL Digital Collections, la page Waseda (avec la mention) ou la lecture
  Aozora. Le lien est déduit des adresses déjà connues, sans appel réseau.
- **Visionneuse intégrée** (décision « les deux ») : désactivée par défaut, activée dans Administration →
  Paramètres. Le manifeste est lu quand l'utilisateur ouvre la visionneuse, puis les vues s'affichent une à une
  (flèches, numéro, taille réelle), avec les mentions de la source. La politique de sécurité n'est élargie qu'à
  `img-src` pour les sites listés (par défaut kokusho.nijl.ac.jp et dl.ndl.go.jp), et seulement sur cette page.
  Une image venue d'un autre site est refusée, avec un message. Aucun script externe, aucune copie des images.
  Le script est un fichier statique de 40 lignes.
- **Étude** : chaque requête de l'étape NDL est indépendante ; `--plan 3` (défaut) ne refait que cette étape.

Statut : tout est testé en simulation, avec les structures réelles relevées sur le poste. Les tests réels sont
V10-5 à V10-8.

## 8. Correctif 1 de l'étape 3 : intégrations simultanées (incident INC-20261116-5D1D5E)

**Constat (rapport de 22 h 32).** Pendant l'intégration des quelque 17 000 notices d'Aozora Bunko, 8 561 erreurs
« duplicate key … unique_source_record » se sont produites en trois minutes, toutes sur la source Aozora.

**Cause.** Deux intégrations de la même synchronisation ont tourné en même temps. Probablement un double clic
sur « Intégrer », ou le bouton « Reprendre », que l'étape 2 affichait pendant toute l'intégration, même quand
elle tournait encore. Pour une notice nouvelle, chaque intégration constatait qu'elle n'existait pas, puis la
créait. Le verrou de ligne posé par la lecture ne protège rien quand la ligne n'existe pas encore.

**Conséquences.** Aucune donnée abîmée. La contrainte d'unicité de la base a refusé chaque doublon, et l'autre
intégration a bien créé la notice. L'incident ne garde qu'un bruit dans le journal (une entrée, 8 561
occurrences).

**Correction.**
- Une seule intégration à la fois par source, entre tous les processus (navigateur, tâche de fond). C'est un
  verrou consultatif PostgreSQL, libéré à la fin, ou par la base si le processus s'arrête. Il vaut pour les
  synchronisations comme pour les imports de fichiers.
- Une seconde demande est refusée par un message, sans rien relancer. La tâche de fond qui trouve le verrou pris
  s'arrête sans rien faire.
- « Reprendre » n'apparaît que si aucune intégration ne tourne. La page indique combien de notices sont
  intégrées et combien restent.
- Dernier filet : une notice créée entre-temps par une autre opération (une recherche en mode automatique, par
  exemple) devient une mise à jour, au lieu d'une erreur.

Deux tests, dont un qui prend le verrou depuis une autre connexion à la base (749 tests réussis).

## 9. Étape 4 : accès des documents numérisés de la NDL (reporté du lot 3)

**Troisième passage de l'étude (22 h 47).**

| Numérisation | Manifeste IIIF | Autres voies |
| --- | --- | --- |
| 2586959 (contrôle, citée par Japan Search) | HTTP 200, attribution « 国立国会図書館 National Diet Library, JAPAN » | API de notice 200, page 200 |
| 2610271 (contrôle, citée par Japan Search) | HTTP 404 | API de notice 200, page 200 |
| 11164407 (base de l'utilisateur) | HTTP 404 | API de notice 200, page 200 |
| 13434771 (base de l'utilisateur) | HTTP 404 | API de notice 200, page 200 |

La NDL distingue trois niveaux d'accès : Internet (0,61 million de documents), NDL seulement (1,23 million),
envoi aux bibliothèques et aux particuliers inscrits (2,05 million). Japan Search cite des numérisations des
trois niveaux, ce qui explique le 404 de 2610271. La page du document ne contient pas le niveau dans son HTML,
car elle est construite par JavaScript. L'API de notice répond, mais son contenu n'a pas été relevé.

**Règle retenue.** Elle ne s'appuie que sur ce qui a été observé :
- manifeste publié et première image servie → « Document : oui », consultable librement sur Internet ;
- manifeste absent (HTTP 404) → « Document : non vérifié », pas en accès libre sur Internet, accès réservé
  probable. J-ed ne dit pas lequel des deux niveaux réservés s'applique : le manifeste ne l'indique pas. La page
  du document, à un clic, le dit.

**Réalisation.**
- L'adresse du manifeste est construite à partir du numéro de numérisation. Le statut IIIF devient « identifié »,
  avec l'origine « déduit par J-ed ».
- « Vérifier le manifeste IIIF » applique la règle ci-dessus. Un 404 de la NDL n'est plus enregistré comme un
  dysfonctionnement. La conclusion de J-ed est gardée lors des actualisations tant que l'adresse ne change pas.
  Les statuts sont recalculés juste avant la vérification, si bien qu'une notice enregistrée avant cette version
  se vérifie sans autre manipulation.
- La visionneuse intégrée sert aussi les documents NDL en accès libre (site `dl.ndl.go.jp` autorisé par défaut).

Amélioration possible plus tard : lire le niveau exact dans l'API de notice de la NDL, après avoir relevé sa
structure sur le poste.

Quatre tests (753 tests réussis).

## 10. Bilan du lot 10

| Demande | Réalisé | Statut |
| --- | --- | --- |
| U6 — arriver aux documents | « Ouvrir le document » ; visionneuse intégrée facultative ; texte intégral Aozora | testé en simulation ; essais V10-4, V10-7, V10-8 |
| U6 — Aozora Bunko | source à part entière, texte, envoi vers un projet | liste importée sur le poste (21 395 notices au total) ; texte : V10-4 |
| U7 — 日本古典籍総合目録 / Kokusho | recherche sur la base `nij16`, structure réelle | testé en simulation ; essai V10-5 |
| U7 — autres bases du NIJL | bases nij01 à nij22 visibles dans Japan Search, utilisables par « Trouver une base Japan Search » | inchangé |
| U7 — 日本古典文学大系本文データベース | publication arrêtée le 31 mars 2023 | aucun accès possible |
| U7 — Historiographical Institute (SHIPS) | aucune interface automatique (recherche Google intégrée) | lien vers le site seulement |
| U7 — Waseda | connecteur par NDL Search ; lien et mention ; site jamais lu | testé en simulation ; essai V10-6 |
| Accès NDL (lot 3) | règle établie par contrôle positif | essai V10-11 |

Défauts corrigés en cours de lot : registre des connecteurs incomplet (cause des tests instables) ; intégrations
simultanées (incident INC-20261116-5D1D5E) ; robots.txt en erreur lu comme une autorisation.

Hors lot, décidé avec l'utilisateur : la traduction du japonais ancien en trois étapes (plus tard).

## 11. Livrables





- Étape 1 : `japon-explorateur-2.0.0-lot10-etape1.zip` et son empreinte `.sha256`.
- Étape 2 : `japon-explorateur-2.0.0-lot10-etape2.zip` et son empreinte `.sha256`.
- Étape 3 : `japon-explorateur-2.0.0-lot10-etape3.zip` et son empreinte `.sha256`.
- Correctif 1 : `japon-explorateur-2.0.0-lot10-etape3-correctif1.zip` et son empreinte `.sha256`.
- Lot complet : `japon-explorateur-2.0.0-lot10.zip` et son empreinte `.sha256`.
- Protocole : section « Lot 10 » (V10-1 à V10-11).
