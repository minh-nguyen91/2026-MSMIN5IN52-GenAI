# A3 — Contrats JSON sous stress

## Groupe

| **Membre** | **Contribution principale** |
|---|---|
| Ruofan | Conception des JSON Schemas et validation des données |
| Zihao | Générateurs, intégration OpenRouter et stratégie de reprise |
| Yao | CLI, évaluation expérimentale et génération des rapports |

Les membres participent également à l'intégration, à la revue de code, aux tests de bout en bout et à la préparation de la soutenance.

## Sujet

- **Identifiant du catalogue :** A3
- **Problématique :** Dans quelle mesure la complexité d'un JSON Schema affecte-t-elle la capacité d'un grand modèle de langage (LLM) à produire des sorties JSON conformes ? Une stratégie de validation et de reprise permet-elle d'améliorer la fiabilité sans augmenter significativement le coût et la latence ?
- **MVP :** Une application Python permettant de générer des sorties JSON à partir de cinq schémas de difficulté croissante, de valider les résultats, de comparer une stratégie de génération unique (*baseline*) à une stratégie avec reprises (*retry*), puis de calculer les métriques et de générer un rapport expérimental.

## Architecture

Le projet est développé en Python. Son architecture sépare la génération, la validation, la stratégie de reprise, l'exécution des expériences et l'évaluation des résultats.

### Composants principaux

- **JSON Schemas :** cinq schémas de difficulté croissante, stockés dans `src/schemas/`.
- **Validateur :** `src/validator.py` vérifie la syntaxe JSON et la conformité structurelle avec la bibliothèque `jsonschema`.
- **Générateur simulé :** `MockGenerator` permet d'exécuter des tests et des démonstrations sans connexion à un service externe.
- **Générateur réel :** intégration d'OpenRouter à travers une interface compatible avec l'API OpenAI.
- **Stratégie de reprise :** `src/json_stress/retry.py` analyse les erreurs de génération et de validation, transmet un retour au modèle et limite le nombre de tentatives.
- **Expérimentation :** `experiment.py` exécute les campagnes de génération et enregistre les résultats au format JSONL.
- **Évaluation :** `evaluation.py` calcule les métriques globales et les résultats par schéma et par stratégie.
- **Rapports :** `report.py` produit des tableaux CSV, des graphiques PNG et un rapport Markdown.
- **CLI :** `cli.py` permet de lancer les générations, l'évaluation et la production des rapports.

### Flux de données

```text
JSON Schema
     |
     v
Générateur (MockGenerator ou OpenRouter)
     |
     v
Réponse JSON
     |
     v
Parsing et validation JSON Schema
     |
     +---- Valide ----> Enregistrement du résultat
     |
     +---- Invalide --> Analyse des erreurs
                            |
                            v
                     Feedback au modèle
                            |
                            v
                     Nouvelle tentative
                     (si autorisée)
                            |
                            v
                     Enregistrement JSONL
                            |
                            v
                  Évaluation et métriques
                            |
                            v
                 CSV, PNG et rapport Markdown
```

### Configuration du modèle

La campagne finale utilise les paramètres suivants :

| Paramètre | Valeur |
|---|---|
| Fournisseur | OpenRouter |
| Modèle | `qwen/qwen3.5-9b` |
| Temperature | 0.2 |
| Nombre maximal de tokens en sortie | 4096 |
| Tentatives maximales en baseline | 1 |
| Tentatives maximales en retry | 3 |

Le système collecte, lorsque ces informations sont disponibles, les tokens d'entrée et de sortie, la latence, le coût et le statut de disponibilité du coût.

### Structure du projet

```text
groupe-json-stress/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── results/
│   ├── experiment_final.jsonl
│   ├── experiment_summary.csv
│   ├── paired_results.csv
│   └── mock_results.jsonl
├── src/
│   ├── validator.py
│   ├── schemas/
│   │   ├── schema_01.json
│   │   ├── schema_02.json
│   │   ├── schema_03.json
│   │   ├── schema_04.json
│   │   └── schema_05.json
│   └── json_stress/
│       ├── __init__.py
│       ├── cli.py
│       ├── evaluation.py
│       ├── experiment.py
│       ├── generator.py
│       ├── openrouter_generator.py
│       ├── report.py
│       └── retry.py
└── tests/
    ├── test_cli.py
    ├── test_evaluation.py
    ├── test_report.py
    ├── test_retry.py
    └── test_validator.py
```

## Installation

### Prérequis

- Python 3.11 ou version compatible avec les dépendances du projet ;
- Git ;
- une connexion Internet pour les expériences réelles ;
- une clé API OpenRouter pour effectuer de nouvelles générations réelles.

### Cloner le dépôt

```bash
git clone https://github.com/TONGTONG0113/2026-MSMIN5IN52-GenAI.git
cd 2026-MSMIN5IN52-GenAI
git switch feature/json-stress
cd groupe-json-stress
```

### Créer l'environnement virtuel

**Linux / macOS :**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell :**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Installer les dépendances

```bash
python -m pip install -r requirements.txt
```

Les principales bibliothèques utilisées sont `jsonschema`, `openai`, `python-dotenv`, `pandas`, `matplotlib`, `pytest` et `tabulate`.

Les versions des dépendances doivent être figées dans `requirements.txt` afin de faciliter la reproduction des résultats.

### Configurer les variables d'environnement

Copier le fichier d'exemple :

```bash
cp .env.example .env
```

Sous Windows PowerShell :

```powershell
Copy-Item .env.example .env
```

Renseigner ensuite les variables localement dans `.env` :

```dotenv
MODEL_API_KEY=your_api_key
MODEL_BASE_URL=https://openrouter.ai/api/v1
```

Ne jamais publier la clé API ni committer le fichier `.env`. Le fichier `.gitignore` exclut les secrets du dépôt.

## Utilisation

Le projet utilise le répertoire `src` comme chemin d'importation Python.

### Définir le PYTHONPATH

**Windows PowerShell :**

```powershell
$env:PYTHONPATH="src"
```

**Linux / macOS :**

```bash
export PYTHONPATH=src
```

### 1. Lancer une génération simulée

```bash
python -m json_stress.cli generate --schema schema_01.json
```

Exemple avec trois tentatives maximum :

```bash
python -m json_stress.cli generate --schema schema_03.json --max-attempts 3
```

Cette commande utilise `MockGenerator` et ne nécessite pas de clé API. Les résultats sont enregistrés par défaut dans `results/generated_results.jsonl`.

### 2. Lancer une expérience réelle

Vérifier d'abord la connexion au modèle :

```bash
python -m json_stress.experiment --check-only
```

Lancer une campagne de test :

```bash
python -m json_stress.experiment --runs-per-schema 40 --max-attempts 3 --output results/openrouter_experiment.jsonl
```

Reproduire la configuration de la campagne finale :

```bash
python -m json_stress.experiment --runs-per-schema 200 --max-attempts 3 --output results/experiment_final.jsonl
```

Cette campagne comprend cinq schémas, 200 échantillons par schéma et deux stratégies, soit 2 000 résultats.

### 3. Évaluer les résultats

```bash
python -m json_stress.cli evaluate results/experiment_final.jsonl
```

### 4. Générer le rapport

```bash
python -m json_stress.cli report results/experiment_final.jsonl --output-dir results/report
```

Le programme génère notamment les fichiers suivants :

- `metrics_by_schema.csv`
- `metrics_by_schema_strategy.csv`
- `metrics_by_strategy.csv`
- `compliance_by_schema.png`
- `cost_by_strategy.png`
- `latency_by_schema.png`
- `strategy_comparison.png`
- `report.md`

## Tests

Les tests automatisés peuvent être exécutés sans clé API :

```bash
python -m pytest -q
```

**Résultat obtenu sur la version finale :**

```text
53 passed
```

Les tests couvrent notamment :

- les cinq JSON Schemas ;
- les sorties valides et invalides ;
- les champs obligatoires manquants ;
- les types incorrects ;
- les erreurs de parsing et de validation ;
- les erreurs de génération ;
- les réponses tronquées ;
- les nouvelles tentatives et leur limite maximale ;
- les limites de coût et de latence ;
- les commandes CLI ;
- le calcul des métriques ;
- la génération des rapports.

Le `MockGenerator` permet de tester ces fonctionnalités de manière reproductible sans dépendre d'un service externe.

## Résultats et évaluation

### Baseline et protocole expérimental

Deux stratégies sont comparées :

- **Baseline :** une seule génération, sans nouvelle tentative.
- **Retry :** validation de la réponse et nouvelle génération en cas d'erreur, avec transmission des erreurs précédentes au modèle.

La campagne finale utilise OpenRouter et le modèle `qwen/qwen3.5-9b`, avec une température de 0.2 et un maximum de 4096 tokens en sortie.

| Paramètre | Valeur |
|---|---:|
| Nombre de schémas | 5 |
| Échantillons par schéma | 200 |
| Stratégies | 2 |
| Résultats baseline | 1 000 |
| Résultats retry | 1 000 |
| Total | 2 000 |

Chaque échantillon possède un `sample_id` permettant de rapprocher les résultats des deux stratégies.

### Résultats par schéma

| Schéma | Stratégie | Résultats | Conformité initiale | Conformité finale | Tentatives moyennes |
|---|---|---:|---:|---:|---:|
| Schema 01 | Baseline | 200 | 100 % | 100 % | 1,00 |
| Schema 01 | Retry | 200 | 100 % | 100 % | 1,00 |
| Schema 02 | Baseline | 200 | 100 % | 100 % | 1,00 |
| Schema 02 | Retry | 200 | 100 % | 100 % | 1,00 |
| Schema 03 | Baseline | 200 | 95 % | 95 % | 1,00 |
| Schema 03 | Retry | 200 | 96 % | 100 % | 1,04 |
| Schema 04 | Baseline | 200 | 99,5 % | 99,5 % | 1,00 |
| Schema 04 | Retry | 200 | 100 % | 100 % | 1,00 |
| Schema 05 | Baseline | 200 | 100 % | 100 % | 1,00 |
| Schema 05 | Retry | 200 | 100 % | 100 % | 1,00 |

### Comparaison globale

| Métrique | Baseline | Retry |
|---|---:|---:|
| Résultats valides | 989 / 1 000 | 1 000 / 1 000 |
| Conformité finale | 98,9 % | 100 % |
| Coût total enregistré | 0,055469 USD | 0,056277 USD |
| Latence moyenne globale | 2 303,20 ms | 2 347,44 ms |

La stratégie retry améliore la conformité finale observée de 98,9 % à 100 %.

L'augmentation du coût total enregistré est de 0,000808 USD, soit environ 1,46 %. La latence moyenne augmente d'environ 44,24 ms.

### Interprétation

Les schémas les plus simples présentent déjà un taux de conformité de 100 % avec les deux stratégies. Le gain principal apparaît sur le Schema 03, pour lequel la conformité finale passe de 95 % à 100 % avec la stratégie retry.

Le nombre moyen de tentatives de 1,04 pour ce schéma indique que seules quelques générations supplémentaires ont été nécessaires.

Ces résultats suggèrent que la validation suivie d'une reprise peut améliorer la fiabilité des sorties structurées à un coût supplémentaire limité dans la configuration testée.

Il convient toutefois de noter que les deux stratégies effectuent des appels distincts au modèle. Les échantillons sont appariés par `sample_id`, mais les résultats ne représentent pas la réparation directe de chaque sortie baseline. Les performances peuvent également varier avec le modèle, la température, le fournisseur ou la complexité des contraintes.

## Limites et plan B

### Limites connues

- Les sorties des LLM sont probabilistes.
- Les résultats dépendent du modèle et de sa configuration.
- Les conclusions ne peuvent pas être généralisées à tous les modèles.
- Certaines règles métier ne sont pas entièrement exprimables avec JSON Schema.
- Les nouvelles tentatives peuvent augmenter le coût et la latence.
- Les tarifs des fournisseurs externes peuvent évoluer.
- Certains coûts peuvent être estimés lorsque l'API ne fournit pas de valeur fiable.
- La campagne évalue une configuration précise et ne constitue pas une comparaison exhaustive de tous les LLM.

### Dépendances externes

Les nouvelles générations réelles nécessitent une connexion Internet, une clé API valide et un service OpenRouter disponible.

### Plan B : démonstration hors ligne

En cas d'indisponibilité de l'API, de problème réseau, de quota épuisé ou d'absence de clé API, le projet peut être démontré avec `MockGenerator`.

Ce mode permet d'exécuter les tests, de simuler des erreurs, de vérifier la validation, de présenter la stratégie retry et de générer des rapports à partir de résultats existants.

L'évaluation et la génération des rapports peuvent également être reproduites à partir du fichier `results/experiment_final.jsonl`, sans effectuer de nouveaux appels au modèle.

## Répartition du travail

Le travail est organisé autour de trois responsabilités principales :

1. **Schémas et validation :** conception des cinq JSON Schemas, validation des données et tests associés.
2. **Génération et reprise :** interface des générateurs, intégration OpenRouter, gestion des erreurs et exécution des expériences.
3. **CLI et évaluation :** commandes, calcul des métriques, comparaison des stratégies, tableaux, graphiques et rapports.

Les membres contribuent également à l'intégration, à la revue de code, aux tests de bout en bout et à la préparation de la soutenance.

Les noms des membres et leurs contributions individuelles doivent être complétés en fonction de la répartition réelle du travail.

## Licence et références

### Licence

- **Code source :** licence du projet à préciser.
- **Modèle `qwen/qwen3.5-9b` :** vérifier les conditions de licence et d'utilisation applicables au modèle choisi.
- **Données expérimentales :** résultats générés dans le cadre du projet ; leur statut de réutilisation et de redistribution doit être précisé si nécessaire.

### Références techniques

- JSON Schema : https://json-schema.org/
- jsonschema : https://python-jsonschema.readthedocs.io/
- pytest : https://docs.pytest.org/
- pandas : https://pandas.pydata.org/
- matplotlib : https://matplotlib.org/
- OpenRouter : https://openrouter.ai/
- OpenAI Python SDK : https://github.com/openai/openai-python

### Utilisation de l'intelligence artificielle

Des outils d'intelligence artificielle ont été utilisés comme assistance au développement, notamment pour l'implémentation de fonctionnalités, le débogage, l'amélioration des tests, la revue de code et la documentation. Les propositions retenues ont été relues, adaptées et testées avant leur intégration.

