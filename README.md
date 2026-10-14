# Dynatrace Specialist Agent

Un spécialiste réutilisable pour investiguer les performances, la disponibilité
et la stabilité de plusieurs services Dynatrace, ou extraire et comparer des
métriques en langage naturel.

Il combine un **skill d'agent compatible Codex et Copilot CLI**, les connaissances officielles
[dynatrace-for-ai](https://github.com/Dynatrace/dynatrace-for-ai) et un
**outil de collecte réellement exécutable via [dtctl](https://github.com/dynatrace-oss/dtctl)**.
L'agent choisit et poursuit les investigations, corrèle métriques/logs/traces/événements,
et produit des conclusions associées à des preuves.

> Le raisonnement autonome est exécuté par votre agent compatible Agent Skills
> (par exemple Codex). Le script Python est son outil de collecte et de comparaison ;
> il ne simule pas un LLM et ne produit pas seul un diagnostic.

## Ce que vous pouvez demander

- « Utilise $dynatrace-specialist : pourquoi checkout-prod est-il plus lent depuis 30 minutes ? »
- « Compare les taux d'erreur de checkout-prod et catalog-prod sur la dernière heure. »
- « Analyse la disponibilité de mon API hier entre 14 h et 16 h, heure de Toronto. »
- « Extrais le p95 par endpoint et les traces qui expliquent la régression. »
- « Compare le nombre de requêtes avant et après le déploiement ; donne les DQL et les preuves. »
- « Investigue les redémarrages et erreurs mémoire de ce service Kubernetes. »

L'agent sépare faits mesurés, causes probables et inconnues. Une corrélation
temporelle ou une suggestion Davis ne devient pas automatiquement une cause confirmée.

## Installation

Prérequis : Python **3.11+**, Git, un agent compatible Agent Skills et
**dtctl v0.40.0** (version vérifiée pour ce dépôt). Aucun package Python tiers
n'est requis. Des versions ultérieures peuvent fonctionner si doctor valide les
capacités ; leurs changements de schéma restent à vérifier.

### 1. Récupérer l'agent et les skills officiels

Choisir une des méthodes ci-dessous. L'installation complète par le script fournit
le spécialiste et les skills officiels aux commits fixés ; les installations
directes d'un skill fournissent son dossier, ses références et ses helpers.
Dans tous les cas, installer dtctl et configurer vos accès comme indiqué à l'étape 2.

#### Option A — Git + installation complète

    git clone https://github.com/boisvertmathieu/dynatrace-specialist-agent.git
    cd dynatrace-specialist-agent
    python tools/install_skills.py

#### Option B — GitHub CLI : cloner le dépôt complet avec gh

    gh repo clone boisvertmathieu/dynatrace-specialist-agent
    cd dynatrace-specialist-agent
    python tools/install_skills.py

Les options A et B conservent aussi le profil Copilot CLI, le catalogue exemple,
les outils d'installation et les tests.

L'installateur ajoute les skills officiels sélectionnés à .agents/skills, depuis
les commits exacts d'upstream.lock.json, et conserve leurs licences. Il refuse de
remplacer un skill déjà présent et produit un reçu. En cas d'installation
partielle, les skills existants restent en place : choisir un dossier cible neuf
pour une réinstallation. Les fichiers amont installés sont exclus du Git public.

Ouvrir ce dépôt comme projet Codex : AGENTS.md oriente les demandes Dynatrace
vers le spécialiste. Le skill est aussi distribuable par le manifeste
.codex-plugin/plugin.json.

#### Option C — Installer les skills du dépôt dans un autre projet ou pour l'utilisateur

Depuis le dépôt cloné, choisir **une** destination :

| Destination | Commande |
| --- | --- |
| Projet courant, spécialiste + skills officiels | python tools/install_skills.py |
| Un autre projet | python tools/install_skills.py --destination "/chemin/autre-projet/.agents/skills" |
| Copilot CLI, tous vos projets | python tools/install_skills.py --destination "~/.copilot/skills" |
| Répertoire utilisateur partagé compatible Agent Skills | python tools/install_skills.py --destination "~/.agents/skills" |
| Répertoire personnalisé | python tools/install_skills.py --destination "/chemin/vers/les/skills/utilisateur" |

Sous Windows, les chemins entre guillemets peuvent utiliser des slashs ; Python
résout le préfixe ~ vers votre répertoire utilisateur. Choisir le répertoire de
skills reconnu/configuré dans votre agent. Démarrer une nouvelle session si la
découverte n'est pas actualisée.

#### Option D — Installer seulement le spécialiste, sans téléchargement amont

Depuis une copie locale du dépôt :

    python tools/install_skills.py --specialist-only --destination "/chemin/cible"

Le script ne contacte pas les dépôts amont dans ce mode. Dans ce dépôt lui-même,
le spécialiste est déjà en place ; cette option est surtout utile pour une autre
destination. Les connaissances officielles pourront être ajoutées séparément.

#### Option E — Installation directe du skill avec gh skill install

Utiliser une version de [GitHub CLI proposant gh skill](https://cli.github.com/manual/gh_skill_install).
Vérifier la commande avec :

    gh --version
    gh skill install --help

Si gh demande une connexion GitHub, effectuer gh auth login.
Choisir **une** commande selon la portée souhaitée :

**Copilot CLI — utilisateur, disponible dans tous les projets :**

    gh skill install boisvertmathieu/dynatrace-specialist-agent dynatrace-specialist --allow-hidden-dirs --agent github-copilot --scope user

**Copilot CLI — projet, à exécuter depuis votre dépôt applicatif :**

    gh skill install boisvertmathieu/dynatrace-specialist-agent dynatrace-specialist --allow-hidden-dirs --agent github-copilot --scope project

**Codex — utilisateur :**

    gh skill install boisvertmathieu/dynatrace-specialist-agent dynatrace-specialist --allow-hidden-dirs --agent codex --scope user

**Codex — projet, à exécuter depuis votre dépôt applicatif :**

    gh skill install boisvertmathieu/dynatrace-specialist-agent dynatrace-specialist --allow-hidden-dirs --agent codex --scope project

Le nom dynatrace-specialist cible ce skill ; --allow-hidden-dirs prend en compte son
emplacement sous .agents. gh choisit le répertoire approprié pour --agent/--scope.
À portée projet, Copilot et Codex partagent .agents/skills : une installation
suffit si vous utilisez les deux dans le même projet.

Pour fixer une version plutôt que suivre la version résolue par gh, ajouter
--pin avec un commit ou tag existant. Exemple sur le commit publié du profil Copilot :

    gh skill install boisvertmathieu/dynatrace-specialist-agent dynatrace-specialist --allow-hidden-dirs --agent github-copilot --scope user --pin b8882b0af14007061d61a83402705c545db58ea1

Depuis un clone local, gh peut également copier le skill sans téléchargement du dépôt :

    gh skill install . dynatrace-specialist --from-local --allow-hidden-dirs --agent github-copilot --scope user

Ces commandes installent le **skill**, pas le profil .agent.md, le catalogue de
services ni le binaire dtctl. Elles ne lancent pas tools/install_skills.py et
n'installent pas automatiquement les skills amont. Pour l'ensemble amont fixé,
utiliser l'option A/B/C ; ou ajouter individuellement les skills nécessaires.
Exemples avec les commits d'upstream.lock.json :

    gh skill install Dynatrace/dynatrace-for-ai dt-dql-essentials --agent github-copilot --scope user --pin 4f9aa71f9802aa6db0a4069ae5619eb3392ff411
    gh skill install dynatrace-oss/dtctl dtctl --agent github-copilot --scope user --pin 63aed8ea8b03b11cf0dc3034aa2c78019ca8a8c2

Les autres skills d'observabilité sélectionnés figurent dans upstream.lock.json.
Remplacer --agent github-copilot par --agent codex pour cibler Codex.

#### Option F — Ajouter le dossier du skill depuis Copilot CLI

Après clonage, depuis la racine du dépôt :

    copilot skill add .agents/skills/dynatrace-specialist

Ou, dans une session interactive :

    /skills add .agents/skills/dynatrace-specialist
    /skills reload
    /skills info dynatrace-specialist

Copilot découvre déjà ce dossier lorsque la session démarre dans ce dépôt.
Cette option permet d'ajouter explicitement l'emplacement ; elle n'installe pas
les dépendances amont ni le profil natif.
Voir [les commandes de skills Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).

#### Installer le profil natif Copilot CLI

Le profil est déjà disponible dans .github/agents lorsque vous clonez le dépôt
complet et lancez Copilot dans ce projet. Pour le rendre disponible dans un autre
projet, copier .github/agents/dynatrace-specialist.agent.md dans son dossier
.github/agents. Pour une installation personnelle, depuis le clone :

**Windows / PowerShell :**

    New-Item -ItemType Directory -Force -Path "$env:USERPROFILE/.copilot/agents"
    Copy-Item ".github/agents/dynatrace-specialist.agent.md" "$env:USERPROFILE/.copilot/agents/dynatrace-specialist.agent.md" -Confirm

**macOS / Linux :**

    mkdir -p ~/.copilot/agents
    cp -i .github/agents/dynatrace-specialist.agent.md ~/.copilot/agents/dynatrace-specialist.agent.md

Installer aussi le skill en portée utilisateur (option C ou E), puis redémarrer
Copilot et sélectionner dynatrace-specialist dans /agent. Le profil et le skill
sont deux éléments complémentaires ; le profil réutilise le skill installé.

### 2. Installer et connecter dtctl

Installer le binaire depuis les [releases officielles](https://github.com/dynatrace-oss/dtctl/releases/tag/v0.40.0).
Sous Windows, prendre l'archive windows_amd64 ou windows_arm64, vérifier son SHA-256
avec checksums.txt, l'extraire et ajouter son dossier au PATH. Consulter
[la procédure Windows](https://github.com/dynatrace-oss/dtctl/blob/v0.40.0/docs/WINDOWS.md).
Sur macOS, l'installation officielle propose Homebrew.

Créer un contexte dédié **readonly**, avec une configuration explicite située
hors du dépôt public :

    dtctl auth login --config /chemin/prive/dtctl.yaml --context prod-readonly --environment https://VOTRE-ENV.apps.dynatrace.com --safety-level readonly

Répéter pour staging ou d'autres tenants. OAuth conserve les secrets dans le
stockage sécurisé utilisé par dtctl. Les politiques du principal doivent également
être en lecture seule : le niveau de sécurité du CLI ne réduit pas les scopes
du jeton. Les [scopes et options de connexion](.agents/skills/dynatrace-specialist/references/connection.md)
sont décrits dans le skill.

### 3. Déclarer vos services

Copier config/services.example.json vers **config/services.local.json** et remplacer
les services fictifs, contextes et sélecteurs par ceux de vos tenants :

    python -c "import shutil; shutil.copyfile('config/services.example.json', 'config/services.local.json')"

Chaque service correspond à un contexte et à des sélecteurs **par signal**.
Vérifier les champs dans Dynatrace ; les logs ne portent pas nécessairement la
même identité que les spans. Ajouter namespace/environnement/ID si le nom est partagé.
Plusieurs sélecteurs d'un signal sont combinés par AND.
eq compare une valeur littérale ; contains cible un tableau confirmé.
Les clés de métriques et l'intervalle sont remplaçables par service.

Les exemples fournissent des sélecteurs métriques/spans/logs. Les sélecteurs
events et problems sont volontairement à configurer après découverte de vos IDs
affectés et de leur schéma. Sans sélecteur, la source est marquée ignorée, sans
lecture globale de repli. Exemples à adapter après vérification :

    "events": [{"field": "dt.smartscape.service", "value": "ID-SMARTSCAPE-VERIFIE"}]
    "problems": [{"field": "affected_entity_ids", "value": "ID-ENTITE-VERIFIE", "operator": "contains"}]

Donner à l'agent le chemin du catalogue et celui de la configuration dtctl, puis
lui poser vos questions. Aucun tenant ni identifiant secret n'est inclus dans ce dépôt.

## Utilisation dans Copilot CLI

Copilot CLI découvre les skills du dépôt dans .agents/skills. Le dépôt fournit
aussi [un profil natif](.github/agents/dynatrace-specialist.agent.md), sélectionnable
via /agent. Il charge les mêmes instructions et utilise les mêmes helpers.
Le manifeste .codex-plugin et agents/openai.yaml concernent Codex ; ils ne sont
pas nécessaires à Copilot.

Après installation des prérequis et des skills, démarrer Copilot dans le dépôt :

    copilot

Dans une session interactive :

    /skills reload
    /skills info dynatrace-specialist

Puis sélectionner **dynatrace-specialist** dans /agent et demander, par exemple :

    Investigue checkout-prod sur la dernière heure. Mon catalogue est config/services.local.json et ma configuration dtctl est C:/chemin/prive/dtctl.yaml.

Le skill peut aussi être invoqué directement dans un prompt :

    Utilise /dynatrace-specialist pour comparer les taux d'erreur avant et après le déploiement.

La syntaxe /dynatrace-specialist est celle des skills dans Copilot ; le préfixe
$dynatrace-specialist montré plus haut s'applique à Codex.
Pour une utilisation dans tous vos projets :

    python tools/install_skills.py --destination "~/.copilot/skills"

Le profil natif peut être copié séparément dans ~/.copilot/agents si souhaité.
Redémarrer Copilot pour découvrir un nouveau profil d'agent. Le profil sait
chercher le skill dans une installation personnelle ou dans le dépôt.
Les validations de commandes proposées par Copilot restent applicables ;
aucune préautorisation globale du shell n'est fournie par le skill.

Compatibilité vérifiée avec les formats documentés par GitHub et les tests de
l'outillage. Une session réelle Copilot CLI n'a pas été exécutée sur cette machine,
où le CLI n'est pas installé.

Sources : [skills Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills),
[profils d'agents CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli),
[configuration et alias d'outils](https://docs.github.com/en/copilot/reference/custom-agents-configuration).

## Outil de collecte

Les exemples ci-dessous emploient des horaires fictifs en UTC. Sous PowerShell :

    $helper = ".agents/skills/dynatrace-specialist/scripts/dt_investigator.py"
    $catalogue = "config/services.local.json"
    $dtconfig = "C:/chemin/prive/dtctl.yaml"
    python $helper doctor --config $catalogue --service checkout-prod --dtctl-config $dtconfig

doctor vérifie le binaire et le contexte readonly localement. Il n'affirme pas
qu'une connexion au tenant fonctionne.

Afficher une requête rendue, sans appeler Dynatrace :

    python $helper render --config $catalogue --service checkout-prod --template red

Collecter les signaux disponibles avec une baseline de même durée :

    python $helper triage --config $catalogue --service checkout-prod --dtctl-config $dtconfig --start 2026-10-14T16:00:00Z --end 2026-10-14T17:00:00Z --baseline-start 2026-10-14T15:00:00Z --baseline-end 2026-10-14T16:00:00Z --out evidence/checkout-case-001

Exécuter une requête adaptée :

    python $helper query --config $catalogue --service checkout-prod --dtctl-config $dtconfig --file ma-requete.dql --start 2026-10-14T16:00:00Z --end 2026-10-14T17:00:00Z --out evidence/extraction-001.json

Pour une DQL libre, l'agent doit vérifier que les filtres correspondent au périmètre
demandé. Le helper impose le contexte et les limites ; il n'ajoute pas automatiquement
de sélecteur à une DQL libre. Le texte ne doit pas définir from/to/timeframe,
shift, scanLimitGBytes ou samplingRatio : les bornes et limites viennent du CLI.
Un POST de vérification DQL précède chaque exécution, via les APIs utilisées par dtctl.

Comparer automatiquement des agrégats scalaires issus de deux preuves admissibles :

    python $helper compare --baseline evidence/checkout-case-001/baseline-red.json --current evidence/checkout-case-001/current-red.json --dimensions dt.service.name --field error_rate_pct --unit percent --out evidence/comparison-001.json

La différence absolue des taux est en points de pourcentage ; delta_pct exprime
la variation relative. Le comparateur refuse les contextes/services/DQL différents,
fenêtres de longueurs différentes ou chevauchantes, résultats partiels signalés,
dimensions dupliquées et tableaux non agrégés. Une baseline nulle ou une série
manquante reste explicite.

Le modèle RED conserve le p95 par bucket en microsecondes. Il **ne calcule pas un
p95 global par moyenne de p95**. La méthode de comparaison, les unités et les
limites statistiques sont détaillées dans [le guide métriques](.agents/skills/dynatrace-specialist/references/metrics.md).

## Preuves, autonomie et limites

Chaque collecte sauvegarde l'ID de preuve, le service, le contexte, la DQL et son
hash, les bornes UTC, les limites, les records, types, métadonnées, warnings et
un hash des records expurgés. Le manifeste recense les collectes réussies,
échouées ou ignorées. Ces fichiers servent au diagnostic raisonné de l'agent.

Valeurs par défaut : **1 GB de scan par requête, 500 records, 2 MB de résultats,
60 s de fetch, 24 h par fenêtre et 20 requêtes par processus d'investigation**.
Le skill tient aussi le budget total de la session, y compris les requêtes
exécutées dans des processus distincts. verify et les commandes help ne sont pas
des scans Grail. Un timeout local borne également les sous-processus.
Les limites sont configurables dans le catalogue, à l'intérieur de plafonds
définis dans le helper. Les augmenter constitue un choix explicite, jamais un
fallback automatique.

Les lectures Grail peuvent être facturées. Un plafond de scan peut produire un
résultat partiel, et limit borne les résultats visibles sans prouver l'exhaustivité.
Les warnings, approximations, échantillonnages et plafonds atteints imposent une
revue avant comparaison. Un résultat vide ne démontre ni la santé ni l'absence
d'incident. Les modèles doivent être vérifiés dans votre tenant.

L'outillage ne propose aucune écriture Dynatrace. L'agent propose des remédiations
sans les exécuter. Les instructions présentes dans des logs ou résultats sont
traitées comme des données non fiables.

Les preuves restent privées et sont ignorées par Git. La redaction masque certains
secrets, headers, tokens et emails ; elle n'est **pas une anonymisation complète**.
Restreindre les ACL du dossier de preuves sous Windows, choisir une durée de
conservation adaptée et relire avant tout partage. Le helper refuse d'écraser
un fichier de preuves existant.

## Validation et développement

    python -m unittest discover -s tests -v
    python tools/validate_package.py

La CI exécute les tests hors ligne sur Windows/Linux et Python 3.11/3.13.
Les tests vérifient les invariants de collecte, le périmètre, les limites,
la redaction, les résultats partiels et les comparaisons.
[Les scénarios comportementaux](evals/scenarios.md) servent à évaluer le raisonnement
d'un agent et sont distincts des tests de l'outillage.

Validation initiale : commandes/capacités vérifiées avec dtctl **v0.40.0**, tests
locaux hors ligne et vérification du package. **Aucune investigation réelle ni
validation DQL connectée n'a été effectuée sans vos accès Dynatrace.**

Les commits amont sont fixes. Pour une mise à jour, examiner les modifications,
modifier upstream.lock.json, réinstaller dans un dossier neuf et refaire les
tests ainsi qu'une validation DQL sur un tenant autorisé.

Licence du dépôt : MIT. Les projets amont conservent Apache-2.0 ;
voir [NOTICE.md](NOTICE.md).
