# Sources et licences

Ce dépôt contient des instructions, requêtes et outils propres à cet agent.
Il s'appuie sur :

- [Dynatrace/dynatrace-for-ai](https://github.com/Dynatrace/dynatrace-for-ai), skills officiels sous Apache-2.0.
- [dynatrace-oss/dtctl](https://github.com/dynatrace-oss/dtctl), CLI et skill sous Apache-2.0.
- [Agent Skills dans Codex](https://developers.openai.com/codex/skills/), pour le format et l'installation.

Les sources amont sont référencées dans upstream.lock.json et téléchargées
uniquement lors de l'installation demandée. Leurs licences sont conservées dans
.upstream-notices du répertoire cible. Les skills et binaires amont ne sont pas
relicenciés par la licence MIT de ce dépôt.
Cet agent n'est pas un produit officiel Dynatrace.
