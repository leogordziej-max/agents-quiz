# Agents quiz : une vidéo quiz par jour, automatiquement

7 agents produisent chaque jour une vidéo quiz de culture générale (format vertical, 30 secondes) :

| Agent | Rôle |
|---|---|
| Léa | choisit 3 thèmes en évitant ceux déjà faits récemment |
| Hugo | écrit 6 questions candidates avec Gemini |
| Inès | vérifie la forme, puis fait vérifier les faits par une seconde IA, et rejette au moindre doute |
| Malo | génère la voix off (Piper, gratuite) |
| Zoé | monte la vidéo |
| Sam | contrôle le format, le son et la durée |
| Noé | prépare la légende (la publication n'est pas encore branchée) |

Tout tourne gratuitement sur GitHub Actions. Ton PC n'est pas nécessaire.

## Installation (une seule fois)

1. **Crée un dépôt** sur GitHub, par exemple `agents-quiz`, en **Public**. C'est nécessaire pour la page gratuite, et rien de secret ne sera dedans.
2. **Envoie les fichiers** : sur la page du dépôt, clique sur *Add file → Upload files*, puis glisse tout le contenu du dossier, y compris le dossier `.github`. Valide avec *Commit changes*.
3. **Crée la clé Gemini** : va sur https://aistudio.google.com, clique sur *Get API key* puis *Create API key*, et copie la clé.
4. **Range la clé en secret** : dans le dépôt, va dans *Settings → Secrets and variables → Actions → New repository secret*. Nom : `GEMINI_API_KEY`. Valeur : ta clé. Ne la mets jamais dans un fichier.
5. **Active la page** : dans *Settings → Pages*, mets *Source* sur **GitHub Actions**.
6. **Premier lancement** : dans l'onglet *Actions*, choisis **Quiz du jour**, puis *Run workflow*.

Ensuite, le quiz se lance tout seul tous les jours à 17:17, heure de Paris en hiver.

## Où voir le résultat

- **Le bureau des agents** : `https://<ton-pseudo>.github.io/agents-quiz/`. Il est mis à jour après chaque lancement.
- **La vidéo** : dans *Actions*, ouvre le dernier lancement, puis *Artifacts → video-du-jour*. Elle est gardée 30 jours.

## Bon à savoir

- **Sans clé Gemini**, Hugo pioche dans `banque_questions.json` (mode secours, 9 questions).
- **Inès réduit les erreurs, mais une IA qui vérifie une autre IA n'est pas infaillible.** Regarde chaque vidéo avant de la publier.
- **L'offre gratuite de Gemini a des limites.** Une vidéo par jour en est très loin. Google peut utiliser les échanges de l'offre gratuite pour améliorer ses produits : c'est sans enjeu pour des questions de quiz.
- **Pour forcer un modèle précis**, ajoute une variable `GEMINI_MODEL` (*Settings → Secrets and variables → Actions → Variables*). Par défaut, le plus récent des modèles « Flash » stables est choisi automatiquement.
