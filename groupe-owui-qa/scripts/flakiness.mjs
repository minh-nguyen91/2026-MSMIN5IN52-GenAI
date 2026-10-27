/**
 * Rapport de flakiness : exécute la suite principale et la baseline N fois.
 *
 *   npm run flakiness            # 10 exécutions
 *   npm run flakiness -- 3       # 3 exécutions
 *
 * Sorties : reports/flakiness.json (brut) et reports/flakiness.md (tableau).
 * La baseline est volontairement en échec ; seuls les échecs de owui signalent
 * un échec de la suite principale. Aucun retry n'est configuré.
 */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runs = Number(process.argv[2] || 10);
const outDir = path.join(root, 'reports');
const playwrightCli = path.join(root, 'node_modules', '@playwright', 'test', 'cli.js');

if (!Number.isInteger(runs) || runs < 1 || runs > 100) {
  console.error('Le nombre de runs doit être un entier compris entre 1 et 100.');
  process.exit(1);
}
if (!fs.existsSync(playwrightCli)) {
  console.error(`Playwright CLI introuvable : ${playwrightCli}. Exécuter npm ci.`);
  process.exit(1);
}
fs.mkdirSync(outDir, { recursive: true });

function git(args) {
  const result = spawnSync('git', args, { cwd: root, encoding: 'utf8' });
  if (result.error || result.status !== 0) {
    throw new Error(`Impossible de lire l’état Git (${args.join(' ')}).`);
  }
  return result.stdout.trim();
}

const gitSha = git(['rev-parse', 'HEAD']);
const workingTreeDirty = git(['status', '--porcelain', '--untracked-files=all']) !== '';

/** Parcourt le rapport JSON de Playwright et rend une ligne par test exécuté. */
function collect(suite, titles = [], out = []) {
  for (const child of suite.suites ?? []) collect(child, [...titles, child.title], out);
  for (const spec of suite.specs ?? []) {
    for (const test of spec.tests ?? []) {
      const result = test.results.at(-1);
      if (!result) continue;
      out.push({
        project: test.projectName,
        title: [...titles.slice(1), spec.title].filter(Boolean).join(' › '),
        status: result.status,
        duration: result.duration,
        error: result.error?.message?.split('\n')[0],
      });
    }
  }
  return out;
}

const stats = new Map();
const runSummaries = [];
let mainSuiteFailed = false;
let expectedTestKeys;

for (let i = 1; i <= runs; i++) {
  const jsonFile = path.join(outDir, `.run-${process.pid}-${i}.json`);
  const started = Date.now();
  let report;
  let commandResult;

  try {
    commandResult = spawnSync(process.execPath, [
      playwrightCli,
      'test',
      '--project=owui',
      '--project=baseline',
      '--reporter=json',
    ], {
      cwd: root,
      stdio: 'ignore',
      env: { ...process.env, PLAYWRIGHT_JSON_OUTPUT_FILE: jsonFile },
    });

    if (commandResult.error) throw commandResult.error;
    if (!fs.existsSync(jsonFile)) {
      throw new Error(`Playwright n’a pas produit le rapport JSON du run ${i}.`);
    }
    report = JSON.parse(fs.readFileSync(jsonFile, 'utf8'));
  } finally {
    fs.rmSync(jsonFile, { force: true });
  }

  const results = collect(report).filter((result) => result.project !== 'setup');
  const mainResults = results.filter((result) => result.project === 'owui');
  const baselineResults = results.filter((result) => result.project === 'baseline');
  const failed = (items) => items.filter((result) => result.status !== 'passed' && result.status !== 'skipped');
  const suiteFailures = failed(mainResults);
  mainSuiteFailed ||= suiteFailures.length > 0 || mainResults.some((result) => result.status === 'skipped');

  const testKeys = results.map((result) => `${result.project}|${result.title}`).sort();
  if (expectedTestKeys && JSON.stringify(testKeys) !== JSON.stringify(expectedTestKeys)) {
    mainSuiteFailed = true;
    console.error(`run ${i}/${runs} : le nombre ou les noms de tests diffèrent des runs précédents.`);
  } else {
    expectedTestKeys ??= testKeys;
  }

  const seconds = (Date.now() - started) / 1000;
  runSummaries.push({
    run: i,
    seconds,
    total: results.length,
    passed: results.filter((result) => result.status === 'passed').length,
    failed: failed(results).length,
    skipped: results.filter((result) => result.status === 'skipped').length,
    suiteTotal: mainResults.length,
    suitePassed: mainResults.filter((result) => result.status === 'passed').length,
    suiteFailed: suiteFailures.length,
    baselineTotal: baselineResults.length,
    baselineFailed: failed(baselineResults).length,
    playwrightExitCode: commandResult.status,
  });

  console.log(
    `run ${i}/${runs} : suite ${mainResults.filter((result) => result.status === 'passed').length}/${mainResults.length} OK, `
    + `baseline : ${failed(baselineResults).length} échec(s) sur ${baselineResults.length} (échec attendu) `
    + `(${((Date.now() - started) / 1000).toFixed(1)} s)`,
  );

  for (const result of results) {
    const key = `${result.project}|${result.title}`;
    const entry = stats.get(key) ?? {
      project: result.project,
      title: result.title,
      passed: 0,
      failed: 0,
      skipped: 0,
      durations: [],
      errors: [],
    };
    if (result.status === 'passed') entry.passed++;
    else if (result.status === 'skipped') entry.skipped++;
    else entry.failed++;
    if (result.error) entry.errors.push(result.error);
    entry.durations.push(result.duration);
    stats.set(key, entry);
  }
}

const rows = [...stats.values()].map((entry) => ({
  ...entry,
  failRate: entry.failed / (entry.passed + entry.failed + entry.skipped),
  avgMs: Math.round(entry.durations.reduce((sum, duration) => sum + duration, 0) / entry.durations.length),
  errors: [...new Set(entry.errors)],
}));
const suite = rows.filter((row) => row.project === 'owui');
const baseline = rows.filter((row) => row.project === 'baseline');
const verdict = (row) => {
  if (row.skipped > 0) return 'ignoré';
  if (row.failed === 0) return 'stable';
  return row.passed === 0 ? 'toujours en échec' : 'FLAKY';
};
const date = new Date().toISOString();
const report = {
  date,
  gitSha,
  workingTreeDirty,
  runs,
  runSummaries,
  tests: rows,
};

fs.writeFileSync(path.join(outDir, 'flakiness.json'), JSON.stringify(report, null, 2));

const md = [
  '# Rapport de flakiness',
  '',
  `${runs} exécutions consécutives le ${new Date(date).toLocaleString('fr-FR')}, sans retry, environnement Docker local (2 tenants + LLM simulé).`,
  '',
  `- Révision Git : \`${gitSha}\` (${workingTreeDirty ? 'arbre de travail modifié' : 'arbre de travail propre'} au début de la campagne).`,
  `- Suite principale : **${suite.length} tests**, ${suite.filter((row) => row.failed === 0 && row.skipped === 0).length} stables, ` +
    `${suite.filter((row) => row.failed > 0).length} en échec ou instables.`,
  `- Exécutions entièrement vertes (suite principale) : **${runSummaries.filter((run) => run.suiteFailed === 0 && run.suitePassed === run.suiteTotal).length}/${runs}**`,
  `- Baseline volontairement fragile : **${baseline.length} tests**, ` +
    `${baseline.reduce((sum, row) => sum + row.failed, 0)}/${runs * baseline.length} échecs attendus.`,
  `- Durée moyenne d'une exécution complète : ${(runSummaries.reduce((sum, run) => sum + run.seconds, 0) / runs).toFixed(1)} s`,
  '',
  '| Projet | Test | Succès | Échecs | Ignorés | Taux d’échec | Durée moy. | Verdict |',
  '|---|---|---:|---:|---:|---:|---:|---|',
  ...rows.map((row) =>
    `| ${row.project} | ${row.title} | ${row.passed} | ${row.failed} | ${row.skipped} | `
    + `${(row.failRate * 100).toFixed(0)} % | ${(row.avgMs / 1000).toFixed(1)} s | ${verdict(row)} |`),
  '',
  '## Erreurs observées',
  '',
  ...rows.filter((row) => row.errors.length).flatMap((row) => [
    `- **${row.project} › ${row.title}** : ${row.errors.map((error) =>
      `\`${error.replace(/\x1b\[[0-9;]*m/g, '').slice(0, 160)}\``).join(' ; ')}`,
  ]),
  '',
].join('\n');
fs.writeFileSync(path.join(outDir, 'flakiness.md'), md);
console.log('\nRapports écrits dans reports/flakiness.json et reports/flakiness.md');

if (mainSuiteFailed) {
  console.error('La suite principale a échoué ou a ignoré au moins un test ; consultez les rapports.');
  process.exitCode = 1;
}
