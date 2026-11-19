---
titre: Argos et IA locale
rubrique: Traduire et résumer
ordre: 110
public: editeur
ecrans: translation:local_engines
resume: Les deux moteurs gratuits qui travaillent sur votre ordinateur.
---
Traduction → **Moteurs locaux**. Les installations sont faites par l'administrateur ; chacun peut consulter l'état.

## Argos Translate (traduction)

Argos fait partie de l'installation standard. Il traduit sans Internet, gratuitement.

### Une traduction en deux temps, par l'anglais

Argos ne traduit **pas directement** du japonais au français. Il fait deux traductions à la suite :

1. du **japonais vers l'anglais** (paquet ja → en) ;
2. puis de **l'anglais vers le français** (paquet en → fr).

Vous ne voyez que le résultat français. Les conséquences :

- **les erreurs s'additionnent** : une ambiguïté mal résolue en anglais est reprise, parfois aggravée, en français ;
- **les noms propres et les titres anciens** sont souvent pris pour des mots ordinaires, puis traduits. Exemple
  constaté : le titre 今様源氏小倉百人一首 devient « M. Yuichi Kokura » ; un nom de collection (九曜文庫) devient un
  nombre ; un nom de lieu devient un mot courant ;
- Argos **n'utilise pas les glossaires**.

À retenir : lisez toujours l'original à côté ; rejetez les propositions manifestement fausses (bouton
**Rejeter**) ; pour un titre, un nom ou un texte important, préférez DeepL ou une IA quand vous êtes en ligne. Si
vous lisez l'anglais, l'étape anglaise est souvent plus fidèle que le français final : une traduction vers
l'anglais seul est envisagée dans une prochaine version.

- **Installer la traduction japonais → français** : récupère les paquets de langues (environ 200 Mo, une seule
  fois), après confirmation.
- **Traduction d'essai Argos** (page « État de l'installation ») : vérifie qu'Argos répond. Elle est aussi faite
  automatiquement deux minutes après une installation ou une mise à jour.
- Qualité : un bon premier jet, à relire. Conseillé pour la file de nuit et les projets confidentiels.

## IA locale (Ollama) : facultative

Une IA qui tourne sur votre ordinateur : gratuite, et rien ne quitte l'ordinateur. Elle fait les **résumés IA**
et, si vous la choisissez, des traductions par IA. Plus lente qu'une IA en ligne, et de qualité moindre.

**Installer le service** (administrateur) : dans le fichier `.env` de J-ed, la ligne `COMPOSE_PROFILES` doit
contenir `ollama` :

```
COMPOSE_PROFILES=argos,ollama
```

Une seule ligne `COMPOSE_PROFILES` dans tout le fichier : s'il y en a deux, seule la dernière compte (la
vérification `verifier-j-ed.ps1` le signale). Puis `docker compose up -d`.

**Choisir un modèle** : section « IA locale », la liste indique la taille de chaque modèle et la mémoire nécessaire.
Cochez « télécharger … depuis Internet », puis **Installer**. Le téléchargement est suivi (pourcentage) et reprend
s'il est coupé. À la fin, un **résumé d'essai** vérifie que tout marche.

Ensuite : Traduction → Moteurs → **Résumés IA** → « IA locale » et le modèle installé.

**Mémoire** : un modèle moyen occupe environ 4 Go pendant un résumé, puis quitte la mémoire après 5 minutes sans
demande. Argos et l'IA locale ne tiennent pas toujours ensemble en mémoire : J-ed évite de les faire travailler en
même temps la nuit.
