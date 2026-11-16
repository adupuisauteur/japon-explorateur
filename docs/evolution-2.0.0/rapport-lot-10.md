# Rapport du lot 10 — documents et nouvelles sources (2.0.0)

*État : étape 1 livrée (étude des sources sur le poste).*

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

## 4. Livrables de l'étape 1

- Archive `japon-explorateur-2.0.0-lot10-etape1.zip` et son empreinte `.sha256`.
- Protocole : section « Lot 10 » (V10-1).
