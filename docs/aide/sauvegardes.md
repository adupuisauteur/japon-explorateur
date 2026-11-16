---
titre: Sauvegardes et restauration
rubrique: Administration
ordre: 30
public: admin
ecrans: backups:list
resume: Sauvegarder, vérifier, copier hors de Docker, restaurer.
---
Administration → **Sauvegardes**. Une sauvegarde contient la base complète, les fichiers d'import, les archives, les
exports et un manifeste d'empreintes.

- **Créer une sauvegarde**, ou laisser faire la sauvegarde automatique (Paramètres).
- **Vérifier** : contrôle l'intégrité. Une sauvegarde non vérifiée n'est pas considérée comme fiable.
- **Copie hors de Docker** : avec `DOSSIER_SAUVEGARDES=C:\chemin\vers\sauvegardes` dans `.env`, chaque sauvegarde est
  copiée dans ce dossier de Windows. Le script de mise à jour le règle pour vous.
- J-ed ne supprime **jamais** ces copies : faites le ménage vous-même si la place manque.

## Restaurer

**Restaurer…** remplace la base actuelle par celle de la sauvegarde. Les fichiers de la sauvegarde sont ajoutés ou
remplacés ; les plus récents sont conservés. J-ed crée d'abord une **sauvegarde de sécurité**, puis demande de taper
`RESTAURER`. Tout ce qui a été saisi après la sauvegarde restaurée est perdu.

Le **guide d'installation** décrit aussi la restauration en ligne de commande, quand J-ed ne démarre plus.
