# F1 — QA E2E d’Open WebUI

Suite de tests Playwright pour vérifier des parcours de chat, RAG et outils
dans Open WebUI, ainsi que l’isolation entre deux instances (tenants) et entre
utilisateurs. L’environnement local utilise un mock LLM déterministe afin de
ne pas dépendre d’une API payante ni d’un GPU.

## Sujet et objectif

- **Catalogue :** F1 — QA E2E d’Open WebUI (difficulté 3/5).
- **Problématique :** vérifier par des tests reproductibles le comportement
  visible et les frontières d’accès d’Open WebUI, y compris les réponses
  d’erreur, les bases de connaissances RAG et l’exécution d’un outil.
- **MVP :** tests Playwright, fixtures avec données jetables et isolées,
  captures et traces lors d’échecs, exécution Docker reproductible, et
  mesure de stabilité sur dix exécutions.

## Architecture

```text
Navigateur Playwright
        |
        +--> Open WebUI tenant A : http://localhost:3000
        |        |-- volume de données A
        |        +-- LLM et embeddings --> mock-llm
        |
        +--> Open WebUI tenant B : http://localhost:3001
                 |-- volume de données B
                 +-- LLM et embeddings --> mock-llm

mock-llm : http://localhost:11500
```

- `docker-compose.yml` lance deux instances Open WebUI `v0.11.4` et un
  serveur Node.js simulant une API compatible OpenAI.
- `e2e/fixtures/` fournit les comptes administrateurs par tenant, des
  utilisateurs temporaires, des bases RAG avec fichiers synthétiques et un
  outil temporaire dont l’exécution est enregistrée par le mock.
- `e2e/tests/` couvre les connexions, le chat/streaming, les erreurs, le RAG,
  l’isolation et les rôles.
- `e2e/baseline/` contient une baseline de streaming volontairement fragile.
- `reports/` contient les rapports de stabilité générés par
  `scripts/flakiness.mjs`.

Les préparations rapides et les contrôles d’autorisation peuvent employer
l’API Open WebUI. Les parcours RAG et outil comprennent aussi une interaction
avec l’interface : la base est jointe au chat, la source est vérifiée dans la
réponse, et le test outil contrôle un reçu d’exécution indépendant du texte
affiché par le modèle simulé.

## Prérequis

- Git.
- Node.js 22 ou ultérieur recommandé et npm (Playwright demande Node.js 20+).
- Docker Desktop ou Docker Engine avec le plugin `docker compose`.
- Chromium installé pour Playwright.
- Ports locaux libres : `3000`, `3001` et `11500`.
- Environ 2 Go de mémoire disponibles pour les services de test.

Aucun GPU, clé de fournisseur LLM ou appel payant n’est nécessaire pour la
configuration par défaut. Le premier téléchargement des images Docker requiert
un accès réseau.

## Installation et configuration

Depuis ce dossier (`groupe-owui-qa`) :

```bash
npm ci
npx playwright install chromium
cp .env.example .env
```

Ouvrir `.env` localement et renseigner `OWUI_EMAIL` et `OWUI_PASSWORD` avec un
compte de test dédié. `npm run seed` crée ce compte comme administrateur sur
les deux tenants. Les deux valeurs doivent être identiques sur A et B.
N’inscrire aucun mot de passe réel, token ou clé API dans Git. Le fichier `.env`
est ignoré par Git.

Les autres variables de `.env.example` pointent vers les URL locales des deux
tenants. Le mock LLM est le fournisseur par défaut ; les variables optionnelles
de fournisseur réel ne sont pas nécessaires à l’exécution normale de cette
suite.

## Démarrer et arrêter l’environnement

```bash
npm run env:up
npm run seed
```

`env:up` attend les healthchecks Docker. Les services attendus sont `owui-a`,
`owui-b` et `mock-llm`. Open WebUI est accessible sur les ports `3000` et
`3001`; le mock écoute sur `11500`.

Après les tests :

```bash
npm run env:down
```

Cette commande arrête les services et conserve leurs volumes. **Ne pas utiliser
`npm run env:reset` pour un arrêt ordinaire : cette commande exécute
`docker compose down -v` et supprime les volumes de données.**

## Tests Playwright

```bash
npm test
```

La commande lance le projet Playwright `owui`, avec un worker afin de partager
l’instance sans exécutions concurrentes. Le setup se connecte via l’interface
et écrit son état d’authentification dans `.auth/`, répertoire ignoré par Git.

Pour inspecter ou lancer d’autres suites :

```bash
npx playwright test --list
npm run test:baseline
npm run report
```

La baseline n’est pas incluse dans `npm test` : son échec est intentionnel et
sert à comparer une attente naïve avec l’assertion réessayée du scénario de
streaming robuste.

Les traces Playwright et screenshots sont configurés pour être conservés en
cas d’échec. Localement, ils sont écrits dans `test-results/`; le rapport HTML
est généré dans `playwright-report/`. Ces répertoires sont ignorés par Git.
Après un test, consulter le rapport avec `npm run report` ou ouvrir une trace
avec `npx playwright show-trace test-results/<dossier>/trace.zip`.

## Couverture et isolation

- **Connexion :** session active, mauvais mot de passe et connexion d’un
  utilisateur standard.
- **Chat :** réponse en streaming, flux irrégulier, persistance et erreur LLM.
- **RAG :** réponse issue du document synthétique, connaissance visible dans
  l’espace de travail et parcours navigateur avec citation de la source.
- **Outils :** un outil sélectionné dans le chat est appelé réellement ; il
  envoie un reçu au mock, que le test vérifie séparément.
- **Multi-tenant et rôles :** refus d’un jeton sur l’autre tenant, invisibilité
  des ressources, séparation des conversations et refus des opérations
  d’administration à un utilisateur standard.

Les noms des utilisateurs, bases et outils de test sont uniques. Les fixtures
suppriment les utilisateurs, bases, fichiers et outils temporaires après le
scénario, y compris lorsque les assertions échouent. Les tests de persistance
et d’outil suppriment leurs conversations ; les scénarios chat génériques,
d’erreur et la baseline peuvent laisser des conversations de test dans les
volumes persistants. Le reçu d’exécution de l’outil est aussi supprimé.
Les tests ne supposent pas l’ordre d’exécution ; Playwright est néanmoins
configuré avec un seul worker pour limiter la contention sur Open WebUI.

## Résultats vérifiés

La dernière exécution locale documentée de `npm test` a donné **17/17 tests
réussis en 36,0 secondes** : le setup d’authentification et 16 scénarios
fonctionnels. Environnement : deux tenants Open WebUI `v0.11.4`, mock LLM
local et navigateur Chromium.

Ce résultat est une exécution locale, pas une preuve d’exécution GitHub Actions.
Les résultats peuvent varier selon la machine, les téléchargements Docker et
la disponibilité des ports.

## Rapport de flakiness sur dix exécutions

Avec les services démarrés et les comptes initialisés :

```bash
npm run flakiness
```

Le script lance dix fois les tests `owui` et la baseline, sans retries. Il
écrit les données détaillées dans `reports/flakiness.json` et le tableau dans
`reports/flakiness.md`. Les fichiers mentionnent la révision Git et signalent
si l’arbre de travail était modifié au début de la campagne.

La baseline naïve est volontairement en échec : ses échecs sont rapportés
explicitement et séparément des échecs de la suite principale. Un run n’est pas
considéré comme entièrement vert si un test de la suite principale échoue ou
est ignoré. Pour une mesure rattachable à un commit, lancer la campagne après
avoir commité les changements concernés et conserver le SHA correspondant.

**Campagne locale vérifiée le 26 octobre 2026 :** 16/16 scénarios principaux
ont réussi lors de chacun des dix runs (160/160 exécutions de scénarios,
0 échec, 0 test ignoré). La baseline a échoué 10/10 fois, comme prévu par sa
conception. La durée moyenne d’un cycle complet, baseline incluse, était de
44,2 secondes. Le rapport identifie le commit
`33073604c9344383dc823aee1e53946076d3f6b7` et signale que l’arbre de travail
était modifié au début de la campagne ; ce SHA désigne donc le commit de base,
pas à lui seul l’ensemble des modifications locales testées.

## Intégration continue

`ci/e2e.yml` contient le workflow prévu : installation Node 22, création de
comptes éphémères, démarrage des deux tenants et du mock, installation de
Chromium, exécution de `npm test`, puis publication du rapport et des traces
comme artifacts.

**La présence de ce fichier ne signifie pas que GitHub Actions l’exécute.**
GitHub ne découvre les workflows que dans `.github/workflows/` à la racine du
dépôt ; `ci/e2e.yml` est conservé dans le dossier du groupe et aucun run CI
n’est revendiqué dans ce README.

Pour l’activer, une personne autorisée (par exemple le propriétaire du fork ou
l’enseignant) doit, sur le fork, créer `.github/workflows/` à la racine si
nécessaire, puis y copier `groupe-owui-qa/ci/e2e.yml` sous le nom
`groupe-owui-qa-e2e.yml`. Elle doit examiner puis committer ce fichier dans le
fork, sans modifier la copie source du groupe. La charte interdit au groupe de
modifier `.github/` à la racine. Une fois le workflow ajouté, la personne
autorisée doit s’assurer que les Actions sont permises dans les paramètres du
dépôt ; elle peut ensuite déclencher un run par un push contenant une
modification sous `groupe-owui-qa/`, ou manuellement dans l’onglet **Actions**
avec **Run workflow**. La définition prévoit ces deux déclencheurs. Vérifier
qu’un run se termine avec succès et que ses artifacts (rapport, traces et
captures) sont disponibles avant d’affirmer que la CI fonctionne.

## Limites connues et démonstration

- Le mock apporte des réponses déterministes et permet de tester l’intégration
  de l’application sans valider la qualité d’un vrai modèle génératif.
- Les deux tenants sont deux instances locales séparées, pas un test de
  déploiement distribué ou de sécurité de production.
- Les sélecteurs UI dépendent de la version d’Open WebUI ; l’environnement est
  fixé à `v0.11.4` dans Compose.
- Aucun run GitHub Actions n’est confirmé ici. La reproductibilité CI dépend
  de l’activation du workflow par une personne autorisée.
- Pour une démonstration sans fournisseur externe, après l’installation et la
  configuration de `.env` décrites plus haut, exécuter depuis ce dossier :

  ```bash
  npm run env:up
  npm run seed
  npm test
  npm run env:down
  ```

  Le mock local sert de fournisseur pour les scénarios ; aucun compte externe
  ni appel payant n’est requis.
- Le budget LLM de la configuration par défaut est nul ; le coût éventuel se
  limite aux ressources locales et à la bande passante de téléchargement.

## Contributions des membres et assistance IA

Le projet F1 — QA E2E d'Open WebUI a été réalisé en binôme.

`Will — @Will-emma`
Mise en place initiale de l'environnement Docker (deux tenants Open WebUI et mock LLM), structure du projet, premiers tests Playwright, fixtures et configuration de l'environnement de test.

`Yan — @StarkMac22`
Finalisation des parcours RAG et outils dans le navigateur, amélioration des fixtures et du mock LLM, validation de la suite Playwright (17/17), exécution et analyse de la campagne de stabilité (160/160), finalisation de la documentation et des rapports.


**Méthode de collaboration :** développement sur des branches Git dédiées, commits distincts, vérifications locales et intégration du travail dans le fork collectif avant la Pull Request vers le dépôt du cours.


**Assistance par IA :** Codex et claude ont assisté la rédaction et la mise à jour de
fichiers du projet.

## Licence et références

- Open WebUI : image `ghcr.io/open-webui/open-webui:v0.11.4`; consulter les
  conditions de licence et notices de la version utilisée.
- Dépendances Node.js : versions verrouillées dans `package-lock.json` ;
  consulter leurs licences upstream.
- Documentation : [Open WebUI](https://docs.openwebui.com/),
  [Playwright](https://playwright.dev/docs/intro) et
  [GitHub Actions](https://docs.github.com/en/actions).


### Support de soutenance

La présentation du projet est disponible dans
[`slides/F1-QA-E2E-Open-WebUI.pptx`](slides/F1-QA-E2E-Open-WebUI.pptx).