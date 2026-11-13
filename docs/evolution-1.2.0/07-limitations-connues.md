# Limitations connues — version 1.2.0

## Sources documentaires

1. **Aucun connecteur n'a été testé en conditions réelles.** Les serveurs japonais n'étaient pas joignables depuis l'environnement de développement, et vous avez choisi de ne pas modifier ses autorisations réseau. Les tests en simulation reproduisent les formats documentés, pas forcément toutes les particularités des réponses réelles. → Protocole de vérification, tests C1 à C8.
2. **CiNii exige un identifiant d'application** (gratuit, sur demande auprès de NII). Sans lui, les deux sources CiNii affichent « Configuration incomplète ».
3. **Japan Search** ne diffuse que les métadonnées que chaque institution autorise par API. Certaines bases sont listées « non diffusées » : elles restent en consultation externe.
4. **Archives nationales** : interrogées via Japan Search (base `najda`) et non par une API propre, qui n'a pas été identifiée. Les images se consultent sur la Digital Archive.
5. **Waseda, Kyoto, Tokyo HI/SHIPS, Nichibunken, presse ancienne** : pas d'API de recherche publique identifiée. Ces sources sont en consultation externe, ou passent par « Trouver une base Japan Search » si l'institution y diffuse sa base.
6. **Japan Search** : aucun paramètre « titre » documenté. Une recherche avancée par titre y est transmise comme mot-clé supplémentaire (combinaison ET).
7. **Variantes de graphie** : au plus 3 variantes interrogées en plus du terme principal pour NDL et CiNii (réglable par source : `max_variants`). Les variantes de noms au-delà des règles automatiques (ex. 千代女房) doivent être saisies ou enregistrées dans le référentiel des noms, car elles ne sont pas devinées.
8. **Téléchargement de documents** : l'application ouvre les notices et les documents numérisés sur le site de l'institution, mais ne télécharge pas les documents. Le journal prévoit déjà le module « Téléchargement » pour une évolution ultérieure.
9. **Mise à niveau de l'installation principale** : la source « National Archives of Japan » d'une installation existante reste « À étudier ». Pour l'activer, utilisez « Trouver une base Japan Search » (recherche 国立公文書館). La source est préconfigurée seulement dans une installation neuve.

## Journal des dysfonctionnements

10. Chaque incident conserve le détail de ses **200 dernières occurrences**. Le compteur reste exact au-delà, mais la comparaison « avant / après correction » ne porte que sur les occurrences conservées.
11. Le **regroupement** repose sur une empreinte simple (module, source, catégorie, code technique, message sans chiffres ni adresses). Deux problèmes différents au message identique sont donc regroupés, et un même problème au message variable peut produire plusieurs incidents.
12. Le changement de statut est réservé au **rôle administrateur**. Les autres rôles consultent et signalent.
13. Les **sauvegardes**, les **exports** de documents et le **module IA** ne sont pas encore reliés au journal (§10 du cahier : extensions ultérieures). Seules leurs erreurs inattendues qui provoquent une page d'erreur sont capturées, par la journalisation générale. Leurs échecs gérés (par exemple une sauvegarde en échec) restent signalés dans leurs propres écrans.
14. Le masquage des secrets repose sur une liste de noms de paramètres et sur des motifs connus. Un secret au format inhabituel, saisi en texte libre dans un signalement manuel, pourrait échapper au masquage : **relisez l'aperçu avant tout export**, comme le rappelle l'écran.
15. L'origine « Réseau » est déduite de l'échec de résolution DNS ou de l'échec simultané de plusieurs sources. C'est une indication, pas une certitude.

## Environnement

16. **Démarrage Docker non exécuté par le développeur.** Le registre Docker Hub n'était pas joignable depuis l'environnement de développement. La configuration Compose a été validée hors ligne, et la séquence de démarrage (migrations, sources, fichiers statiques, Gunicorn en mode production, redémarrage) a été testée sans Docker. → Vérification sous Windows : guide d'installation et tests V1, V2 et V12 du protocole.
