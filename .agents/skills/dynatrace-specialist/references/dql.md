# DQL et schémas

Les requêtes locales sous queries/ sont des points de départ paramétrés,
pas des schémas universels validés dans tous les tenants. Le helper échappe les
valeurs JSON, valide les noms de champs et interdit les paramètres de source
qui remplacent la fenêtre ou les limites de collecte. Utiliser --file pour une
DQL adaptée aux champs découverts ; --start/--end fixent la période hors du texte.
Une correction de la DQL doit être vérifiée par dtctl verify query avant exécution.
Cette vérification appelle Dynatrace : ce n'est pas un parseur hors ligne.

Découverte ciblée, après choix explicite du contexte et de la fenêtre :

    describe spans
    fieldsSnapshot metrics, by: {metric.key}
    | filter startsWith(metric.key, "dt.service.request.")
    | fields metric.key, field, type
    | limit 100

Ne pas supposer que service.name, dt.service.name, dt.entity.service et
dt.smartscape.service sont interchangeables. Le modèle Smartscape actuel utilise
smartscapeNodes "SERVICE", getNodeName et des IDs Smartscape ; un tenant plus ancien
peut nécessiter des requêtes différentes. Découvrir les champs d'identité et les
relations dans le tenant et charger le skill dt-migration si installé/pertinent.

Un sélecteur contains utilise in(valeur, champ_array) et doit cibler un tableau
confirmé. Un sélecteur eq utilise l'égalité littérale, jamais une expression DQL
libre issue du catalogue. Ajouter les dimensions d'environnement nécessaires.

Les champs de log usuels sont content et loglevel ; des pipelines personnalisés
peuvent employer d'autres champs. Les modèles problems utilisent event.status,
event.name et les champs Davis. ACTIVE et CLOSED sont les valeurs usuelles,
pas OPEN. Vérifier dt.davis.is_duplicate et la forme des identifiants affectés.
Pour les spans, request.is_root_span est utile pour OneAgent ; le root d'une trace
OpenTelemetry entière n'est pas automatiquement le point d'entrée de chaque service.
Un fallback span.kind == "server" doit être explicitement adapté et expliqué.

Règles d'analyse :

- Filtrer tôt, projeter les champs utiles et agréger avant un limit lorsque la
  demande porte sur une fréquence ou un taux.
- Trier avant de sélectionner des traces lentes ou des logs récents.
- Garder les unités et les bornes dans les preuves ; ne pas déduire une résolution
  fixe de bins.
- Les scans partiels et l'échantillonnage limitent les conclusions négatives.
- Les preuves contiennent le texte, un hash, les limites, les types, métadonnées
  et warnings. Les syntaxes ne sont dites validées dans le tenant qu'après succès
  réel de verify et query.

Références :
[essentiels Dynatrace, commit fixé](https://github.com/Dynatrace/dynatrace-for-ai/tree/4f9aa71f9802aa6db0a4069ae5619eb3392ff411/skills/dt-dql-essentials),
[services](https://github.com/Dynatrace/dynatrace-for-ai/tree/4f9aa71f9802aa6db0a4069ae5619eb3392ff411/skills/dt-obs-services),
[tracing](https://github.com/Dynatrace/dynatrace-for-ai/tree/4f9aa71f9802aa6db0a4069ae5619eb3392ff411/skills/dt-obs-tracing),
[CLI DQL v0.40.0](https://github.com/dynatrace-oss/dtctl/blob/v0.40.0/docs/resources/dql-queries.md).
