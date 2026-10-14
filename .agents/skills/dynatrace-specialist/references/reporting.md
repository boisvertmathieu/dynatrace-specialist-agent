# Restitution étayée

Adapter la longueur à la demande. Commencer par le constat principal et son niveau
de confiance, puis donner les mesures et preuves qui permettent de l'évaluer.
Un rapport d'incident complet contient :

1. Service(s), environnement(s), fenêtre UTC et fuseau utilisateur.
2. Impact mesuré : disponibilité observée, latence, erreurs, trafic et population.
3. Chronologie : événement, heure, source et identifiant de preuve.
4. Causes probables classées, mécanisme causal proposé, preuves et alternatives.
5. Prochaines vérifications / corrections proposées, avec leur objectif.
6. Limites : accès, instrumentation, données absentes, échantillonnage, scan partiel,
   limite de résultats, baseline et incertitude résiduelle.
7. Références des preuves : fichier local, ID, DQL et fenêtre. Ajouter un lien
   Dynatrace seulement si son URL réelle a été obtenue ou vérifiée.

Confiance élevée : plusieurs signaux indépendants, chronologie et mécanisme
concordants, alternatives plausibles départagées. Moyenne : corrélation cohérente
avec une vérification causale manquante. Faible : observations limitées ou ambiguës.
Ces niveaux sont qualitatifs, pas des probabilités numériques.
Ne pas appeler cause confirmée une simple corrélation ou une proposition Davis.

Pour une demande de métriques : table valeur/unité/dimension/période, différence
absolue et relative, méthode d'agrégation et référence de preuve suffisent.
Une série manquante et une baseline nulle restent explicites.
Le manifeste de triage est une liste de collectes ; il ne constitue pas un diagnostic.
Ne partager aucun dossier de preuves, log brut ou rapport privé sur le repo public.
