# Mission de ce dépôt

Pour une investigation ou analyse Dynatrace, charger
.agents/skills/dynatrace-specialist/SKILL.md et suivre ses références pertinentes.
Les skills officiels installés complètent les connaissances ; les fonctions
d'écriture qui y figurent ne sont pas autorisées par une demande d'investigation.

Le catalogue de services et la configuration dtctl sont privés et fournis localement.
Ne jamais inventer les identités, accès, métriques ou résultats absents.
Conserver les preuves sous evidence/ ou hors du dépôt, jamais dans un commit.
L'accès de l'agent aux logs, métriques, traces et événements reste en lecture seule.

Pour développer ce dépôt :

    python -m unittest discover -s tests -v
    python tools/validate_package.py

Ne pas utiliser de tenant réel pour les tests CI. Les tests de collecte simulent
dtctl ; la validation réelle des DQL exige une connexion Dynatrace autorisée.
