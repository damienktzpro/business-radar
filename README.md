# Business Radar

Un feed personnel de veille entrepreneuriale, gratuit et automatisé.

## Ce que fait la V1

- récupère les lancements Product Hunt via son flux RSS officiel ;
- récupère Show HN + les meilleures histoires Hacker News via l'API publique ;
- récupère TechCrunch via RSS ;
- classe automatiquement les contenus : IA, SaaS, Startup, Levée, Fintech, E-commerce, France ;
- attribue un score d'intérêt simple sur 100 ;
- affiche le tout dans une interface mobile/desktop ;
- se met à jour automatiquement toutes les 6 heures via GitHub Actions ;
- se publie gratuitement sur GitHub Pages.

## Tester localement

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/collect.py --demo
python -m http.server 8000
```

Puis ouvrir `http://localhost:8000`.

Pour une vraie collecte, exécuter :

```bash
python scripts/collect.py
```

## Mise en ligne gratuite

1. Créer un dépôt GitHub **public** nommé par exemple `business-radar`.
2. Envoyer tous les fichiers de ce dossier sur la branche `main`.
3. Dans **Settings → Pages**, choisir **GitHub Actions** comme source de déploiement.
4. Ouvrir l'onglet **Actions** et lancer `Update Business Radar` une première fois si nécessaire.
5. GitHub affichera ensuite l'URL publique du site.

## Ajouter une source RSS

Dans `scripts/collect.py`, ajouter une entrée à `RSS_SOURCES` :

```python
{
    "name": "Nom du média",
    "url": "https://exemple.com/feed/",
    "type": "news",
    "weight": 6,
},
```

Si une source tombe en panne, le collecteur continue avec les autres et la liste des erreurs apparaît dans `data/feed.json`.

## Coût

La V1 n'utilise aucune API payante et ne nécessite aucune clé API. Elle est conçue pour fonctionner sur les offres gratuites de GitHub pour un petit projet personnel.
