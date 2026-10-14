# Extraire et comparer des métriques

Traduire la demande en contrat : métrique, unité, agrégation, dimensions, population,
contexte, intervalle, fenêtres UTC et format. Découvrir la clé et ses dimensions
avant une analyse nouvelle. Les métriques Grail utilisent timeseries ou metrics,
jamais fetch dt.metric. Des métriques Environment API v2 peuvent utiliser une clé
et un modèle différents : employer leur descripteur réel et ne pas traduire
automatiquement une clé builtin: en clé dt.*.

Les modèles RED utilisent les clés dt.service.request.* et l'unité de response_time
documentée en microsecondes. Vérifier les métadonnées du tenant avant de réutiliser
la conversion en millisecondes. Les durations de spans sont en nanosecondes.
Le modèle RED conserve les tableaux p95_us, requests et failures : le p95 par bucket
ne devient jamais un p95 global par une moyenne. Interroger un percentile scalaire
sur la fenêtre entière si demandé et disponible.

Pour un taux d'erreur de fenêtre : somme des échecs / somme des requêtes,
sur une population et des buckets compatibles. La moyenne des taux par bucket
ou par service est biaisée lorsque les volumes diffèrent.
Ne pas remplacer des nulls par zéro sans sémantique connue : zéro observation,
zéro requête et télémétrie absente sont distincts. Un dénominateur nul donne un
taux inconnu. Les pourcentages ont des différences absolues en points de pourcentage
et des variations relatives en pourcentage : préciser les deux séparément.

Comparer des fenêtres de même durée, même définition DQL, contexte, service,
dimensions, agrégation, instrumentation, unités et résolution. Réinterroger
séparément la baseline avec les mêmes bornes de durée plutôt que bricoler append
sans jointure ou shift mal aligné. Pour des durées différentes, comparer des rates
normalisés et signaler la couverture ; le comparateur automatique les refuse.
Une série apparue/disparue reste missing_data, pas zéro.

Le helper compare refuse les preuves en erreur/review_required, les fenêtres qui
se chevauchent, les définitions différentes, les dimensions dupliquées et les
tableaux non agrégés. Il produit des deltas descriptifs, pas un test statistique,
une validation de causalité ou une correction de saisonnalité.
Le champ et l'unité sont explicites : confirmer leur signification dans la requête
et les types/métadonnées avant la comparaison.
Pour plusieurs services, collecter avec leurs identités respectives puis comparer
dans une table en contrôlant les populations ; le helper compare est volontairement
limité aux variations temporelles d'un même service.

Un count sur des spans échantillonnés ne remplace pas un compteur de requêtes.
Une extraction avec limit est un échantillon borné de résultats, pas la population.
Vérifier warnings, limites de scan/résultats, sampling et approximations dans chaque
preuve. Une exportation exhaustive exige des partitions temporelles adaptées et
une vérification de couverture, dans le budget. Ne pas affirmer son exhaustivité
avec une seule page.

Source : [commandes métriques DQL](https://docs.dynatrace.com/docs/platform/grail/dynatrace-query-language/commands/metric-commands),
[descripteur Metrics API v2](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/metric-v2/get-descriptor).
