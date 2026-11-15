# J-ed 2.0.0 — Demandes de l'utilisateur en cours de développement

Demandes faites pendant le développement, en plus du cahier des charges. Chacune indique le lot où elle est
traitée et son état.

| N° | Date | Demande | Lot | État |
| --- | --- | --- | --- | --- |
| U1 | 15/11/2026 | Valider et adopter en une fois les traductions de plusieurs champs, au lieu d'un clic par champ | 0 | Fait (archive `lot0e`) : bouton « Tout valider et adopter » sur la fiche, la page « Traductions » et la page de la tâche |
| U2 | 15/11/2026 | Exports de fiches : en bas de page, indiquer la date, l'heure, le nom de l'application et l'utilisateur | 1 | À faire, avec le passage au nom J-ed dans les en-têtes des exports |

## U2 — Pied de page des exports

**Aujourd'hui (1.3.0, lot 0)**, le pied de page d'un export Word ou PDF contient le texte libre « Pied de
page », l'identifiant de l'export et le numéro de page. Le site HTML y ajoute le nom et la version de
l'application. La date de production n'apparaît que dans les métadonnées et la page de garde.

**Proposition, à valider au lot 1.** Sur chaque page des exports Word, PDF et HTML, le pied de page indiquerait :

- la date et l'heure de production (heure de Paris) ;
- « J-ed » et sa version ;
- le nom affiché de l'utilisateur qui a produit l'export ;
- l'identifiant de l'export et le numéro de page, comme aujourd'hui.

Le texte libre « Pied de page » de l'export reste possible.

Points à trancher :

- nom affiché ou identifiant de connexion de l'utilisateur ;
- mention de l'utilisateur toujours présente, ou une case « ne pas indiquer mon nom » pour un export destiné
  à être diffusé ;
- même pied de page pour les exports de projets de traduction (texte bilingue Word ou PDF).
