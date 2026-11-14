# Guide d'utilisation — module de traduction (version 1.3.0)

Le module se trouve dans le menu **Traduction** (rôles Administrateur et Chercheur ; le Lecteur n'y a pas
accès). Règles constantes, quel que soit l'écran :

- **Rien n'est envoyé à un service en ligne sans votre confirmation** : chaque traduction passe par un écran
  qui indique le moteur, le volume, le coût estimé, le quota et les glossaires appliqués. Au-delà du seuil
  (20 000 caractères par défaut, réglable), une seconde confirmation est demandée. Avant le **premier** envoi à
  un fournisseur, le résumé de ses conditions d'utilisation des textes s'affiche et vous confirmez l'avoir lu.
- **L'original n'est jamais modifié** : les traductions sont des versions à part, jamais écrasées.
- **Aucune bascule automatique** : si un moteur échoue, l'erreur est expliquée et le deuxième moteur est
  seulement **proposé**.
- Une traduction produite par un moteur **simulé** (Argos sans paquets) porte la mention **« Simulation »**
  partout, exports compris.
- Les montants sont des **estimations** ; la facture du fournisseur fait foi.

## 1. Moteurs (Traduction → Moteurs)

Seul endroit où se choisissent les moteurs : moteur **par défaut** et **deuxième moteur**, clés DeepL et Google
(notices `notice-cle-deepl.md`, `notice-cle-google.md`), Argos (notice `notice-argos.md`, page « Moteurs
locaux »), IA en ligne (§ 9). On y trouve aussi les plafonds mensuels de caractères, le seuil de seconde
confirmation, l'envoi facultatif des segments voisins aux IA comme contexte, et le résumé des conditions de
chaque fournisseur. Un projet peut avoir ses propres moteurs (modification du projet).

## 2. Traduire une notice

Sur la fiche d'une notice : **Traduire…** (ou, dans la Bibliothèque, sélection de notices → « Traduire »).
Choisissez les champs (titre et description ; sujets et lieu en option) et le moteur, puis confirmez. Les
traductions arrivent dans la page **Traductions de la notice**, comme propositions de la couche éditoriale.
**Valider** une traduction l'**adopte** dans la notice (réservé à l'administrateur) ; la notice d'origine garde
son texte original.

## 3. Projets, documents et segments (Traduction → Projets)

1. **Nouveau projet** : titre, langues (japonais → français ou anglais → français), dossier lié, moteurs
   propres, **Confidentiel** (moteurs en ligne refusés ; l'administrateur ne voit que le titre et la taille),
   **Corpus de référence** (§ 7).
2. **Ajouter un document** : collage, fichier .txt (UTF-8, Shift_JIS, EUC-JP, UTF-16 ; aperçu et confirmation
   si l'encodage est incertain), .docx (texte) ou PDF avec texte (pas d'OCR). Variété : moderne, classique
   (bungo), kanbun. Une notice peut aussi être **copiée** dans un projet depuis sa page de traductions.
3. **Écran de travail** : original et traduction en deux colonnes, filtres (non traduits, proposés, validés,
   en alerte), chapitres. Actions par sélection ou par chapitre : traduire, valider les dernières propositions.
4. **Page d'un segment** : toutes les versions (moteur, date, alertes, coût), traduire avec le moteur par défaut
   ou le deuxième, **corriger** (nouvelle version liée), saisir sa traduction, **valider** (une seule version
   validée, par le propriétaire), rejeter, fusionner avec le suivant, diviser, commencer un chapitre, **ajouter
   un terme au glossaire**.
5. Pour une copie de notice, la traduction validée peut être **publiée dans la notice** (action confirmée).

**Mémoire de traduction** : un segment identique à un segment déjà validé dans vos projets reprend sa
traduction comme **proposition**, sans appel au moteur (Traduction → Mémoire : consultation, recherche,
exclusion d'une paire).

## 4. Glossaires (Traduction → Glossaires)

- Entrées : terme, lecture, traduction imposée, catégorie, variantes de graphie, traductions à éviter, remarque,
  source de la décision. Doublons refusés ; import CSV avec vérification préalable ; export CSV.
- Rattachez les glossaires à un projet (page du projet, par ordre de priorité). Les contradictions entre
  glossaires sont affichées.
- **DeepL** : le glossaire n'est appliqué par DeepL qu'après « Envoyer à DeepL » (case de confirmation) ; la
  copie distante peut être supprimée. **IA** : les termes présents sont ajoutés à la consigne. **Google, Argos** :
  pas de glossaire côté moteur.
- Pour tous les moteurs, un **contrôle local** signale (sans corriger) un terme attendu absent ou une traduction
  à éviter présente.

## 5. Suivi des tâches (Traduction → Tâches)

Progression en direct, annulation, **reprise** d'une tâche interrompue (seuls les éléments non traduits sont
envoyés), relance des échecs, proposition du deuxième moteur.

## 6. Exports (Traduction → Exports)

Par projet ou par document, réservés au propriétaire : texte bilingue (.txt, Markdown), tableau CSV, traduction
seule (.txt, Markdown), Word bilingue en tableau. Choix « validées seulement » ou « validées, à défaut dernière
proposition » (signalée « non validée »). En-tête : moteurs utilisés, proportion validée, mention Simulation.

## 7. Évaluation (Traduction → Évaluation)

Cochez « Corpus de référence » sur un projet de textes **non confidentiels** et variés. « Préparer la
comparaison » avec plusieurs moteurs : rien n'est envoyé avant la confirmation du coût de chaque moteur. Les
résultats datés s'affichent côte à côte ; **vous notez** chaque traduction (correcte, acceptable, fautive,
contresens). Aucun score automatique n'est calculé.

## 8. Consommation (Traduction → Consommation)

Par moteur et par mois : tâches, caractères envoyés, traductions reçues, coût estimé (tâches IA comprises),
plafonds du mois en cours, détail des tâches.

## 9. Utiliser les IA en ligne pour traduire

Le module réutilise le **module d'IA** existant (README, § 4 « Intelligence artificielle ») :

1. **IA → Fournisseurs** : saisissez et testez la clé du fournisseur (OpenAI, Anthropic, Gemini ou service
   compatible OpenAI).
2. **Préférences IA** : le mode ne doit pas être « Désactivée », et la case **« Traduction »** du profil actif
   doit être cochée : c'est votre autorisation d'utiliser les IA pour traduire.
3. **Traduction → Moteurs** : choisissez « Intelligence artificielle en ligne », le fournisseur et le modèle,
   comme moteur par défaut ou deuxième moteur.

Chaque appel crée une **tâche IA** (historique et plafond mensuel du module d'IA). Les consignes envoyées sont
dans `apps/translation/reference/consignes-ia.json` (versionnées) ; la réponse doit être un JSON strict, et un
commentaire hors traduction est signalé. Les textes marqués classique ou kanbun reçoivent une consigne adaptée.

## 10. Évolution à venir : Ollama

Ollama (modèles d'IA installés sur votre ordinateur) sera ajouté plus tard comme **moteur local
supplémentaire**, selon ses propres spécifications (version 1.1, protocole O1 à O16). Le module a été conçu pour
cela : un moteur = une classe dans `apps/translation/engines/` et une ligne dans `registry.py`, sans changer le
fonctionnement décrit ici. Le corpus de référence et les comparaisons conservées permettront de comparer Ollama
aux moteurs actuels sur les mêmes textes.
