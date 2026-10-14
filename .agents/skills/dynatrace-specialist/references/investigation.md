# Investigation d'incident

## Délimiter et découvrir

Confirmer l'identité, la période, le symptôme et le niveau d'impact observé.
Examiner les métriques de trafic, erreurs et latence ; chercher les problèmes Davis
qui chevauchent l'incident, y compris ceux qui ont commencé avant la fenêtre.
La requête problems locale est un point de départ, pas une garantie d'exhaustivité
des problèmes actifs anciens. Élargir une requête ciblée ou consulter leur cycle
de vie si nécessaire, dans les limites autorisées.

Découvrir les champs et dimensions réellement présents avec describe,
fieldsSnapshot, metrics et des probes bornées. Les modèles locaux supposent des
sélecteurs déjà vérifiés. Si un selector n'est pas configuré, le triage l'indique
comme ignoré et ne fait pas de lecture globale à sa place.
Tenir compte d'OpenTelemetry, des services OneAgent, de Smartscape et des anciennes
entités ; ne pas mélanger leurs identifiants ni supposer les champs identiques.

## Triage et hypothèses

Une régression RED donne le point de départ, pas la cause.
Construire une chronologie UTC : première anomalie, événement précurseur,
propagation aux dépendances, début/fin d'impact et récupération.
Comparer une fenêtre saine de même durée et, si possible, le même créneau d'une
semaine précédente ; contrôler la saisonnalité, le trafic et les déploiements.

| Symptôme | Vérifications utiles |
| --- | --- |
| Latence | p50/p95/p99 par endpoint, traces lentes, dépendances DB/HTTP, contention, GC, pools, CPU, queues |
| Erreurs | taux pondéré, codes/exception dominants, traces en échec, dépendances, changements de version |
| Disponibilité | trafic attendu, synthetic/SLO/RUM si disponibles, ruptures réseau, pods/endpoints et santé des dépendances |
| Stabilité | redémarrages/OOM, exceptions, GC, pression mémoire, throttling, saturation de pools, évolution temporelle |

Suivre deux ou trois hypothèses pertinentes, avec une preuve qui pourrait les
réfuter. Charger dt-obs-hosts, dt-obs-kubernetes ou le runtime correspondant uniquement
quand la topologie ou les observations le justifient.

## Corréler

Partir des trace.id, span.id, identifiants de service, pod/process/host, noms d'endpoint
et versions vérifiés. Examiner les spans parents/enfants, leurs timestamps et la
direction client/server pour départager cause, propagation et symptôme.
Ne pas sommer naïvement les durées de spans imbriqués comme si elles étaient exclusives.
Corréler les logs par trace.id si propagé ; sinon utiliser entité + fenêtre courte
et annoncer que la corrélation est moins forte.
La proximité temporelle d'un déploiement ne prouve pas sa responsabilité.
Une cause Davis est une proposition issue du moteur, à corroborer.

Pour chaque hypothèse, conserver : preuves favorables, contre-preuves, couverture
des sources, confiance qualitative et prochaine requête discriminante.
Un service silencieux peut être hors trafic ou non instrumenté ; ne pas le déclarer
en panne à partir d'une absence de requêtes ou de logs.

## Arrêt et restitution

Poursuivre les lectures qui peuvent changer le diagnostic, en tenant un budget
global même si plusieurs processus helper sont utilisés. triage gère son budget
local ; l'agent tient le total de la session.
Arrêter les essais sans information nouvelle. Expliquer les limites, proposer
une vérification ou correction concrète, et ne pas exécuter de remédiation.
Le rapport final cite les preuves et sépare l'impact mesuré de l'impact supposé.
