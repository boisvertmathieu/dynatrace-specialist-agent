# Connexion à plusieurs environnements

Le catalogue privé associe chaque clé de service à un contexte dtctl et des sélecteurs
par signal. Les alias servent au raisonnement, pas à la sélection automatique du CLI.
Une chaîne de service ne garantit pas une identité unique : ajouter une dimension
d'environnement, un namespace ou un identifiant vérifié si le nom est partagé.

Passer toujours les chemins explicites du catalogue et de la configuration dtctl.
Le helper exécute le CLI dans un répertoire temporaire : une .dtctl.yaml déposée dans
un projet ou dans des preuves ne doit pas changer le tenant. Les accès sont gérés
par dtctl, sans jamais intégrer un jeton au catalogue de services.

Configuration initiale, hors investigation :

    dtctl auth login --config /chemin/prive/dtctl.yaml --context prod-readonly --environment https://ENV.apps.dynatrace.com --safety-level readonly

OAuth interactif utilise les droits de l'utilisateur ; readonly ne retire pas les
permissions du jeton. Préférer un principal aux droits restreints. Pour une intégration
machine, provisionner un OAuth client en lecture seule et demander explicitement
les scopes nécessaires avec --scopes ; conserver les secrets dans un gestionnaire
de secrets ou les variables d'environnement prévues par dtctl, jamais en arguments.
L'agent ne crée pas de principal et ne modifie pas IAM.

Scopes Grail utiles, selon la source :

| Source | Scope |
| --- | --- |
| Métriques | storage:metrics:read |
| Logs | storage:logs:read |
| Spans | storage:spans:read |
| Événements et problèmes | storage:events:read |
| Entités / Smartscape | storage:entities:read |
| Découverte système | storage:system:read |

Des politiques IAM et restrictions de buckets peuvent limiter ces scopes.
Ne pas demander des scopes d'écriture pour contourner une erreur de lecture.
Ne pas confondre une erreur de lecture d'une source avec un tenant indisponible.
dtctl auth whoami n'est pas un test de lecture Grail fiable pour tous les types de jetons.

L'accès MCP Dynatrace est facultatif : consulter le schéma réellement exposé et
les scopes documentés. Exécuter uniquement les outils de lecture, avec les mêmes
bornes, identités et preuves. Le chemin implémenté et testé dans ce dépôt est dtctl ;
aucun serveur MCP ni endpoint d'API non documenté n'est supposé.

Sources : [dtctl configuration](https://github.com/dynatrace-oss/dtctl/blob/v0.40.0/docs/CONFIGURATION.md),
[scopes DQL](https://github.com/dynatrace-oss/dtctl/blob/v0.40.0/docs/resources/dql-queries.md),
[MCP Dynatrace](https://docs.dynatrace.com/docs/shortlink/dynatrace-mcp-server).
