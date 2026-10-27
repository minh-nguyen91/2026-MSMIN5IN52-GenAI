/**
 * BASELINE — la façon naïve d'attendre une réponse en streaming.
 *
 * Ce test est VOLONTAIREMENT fragile : il sert de point de comparaison pour
 * le rapport de flakiness, et n'est pas lancé par `npm test`.
 *
 * Il utilise le helper du cours `chat()`, qui attend que la réponse contienne
 * quelques caractères, patiente 500 ms, puis lit le texte UNE fois. Si le
 * modèle n'a pas fini de streamer à cet instant, le texte lu est tronqué.
 *
 * La version robuste du même scénario est dans e2e/tests/02-chat.spec.ts
 * (« réponse longue au débit irrégulier ») : elle utilise une assertion
 * auto-réessayée (toContainText) qui attend le texte complet.
 */
import { test, expect, MODEL, LONG_QUESTION, uid } from '../fixtures/owui';
import { startNewChat, selectModel, chat } from '../helpers/chat';

test('baseline naïve : lecture unique après un délai fixe', async ({ page }) => {
  await startNewChat(page);
  await selectModel(page, MODEL);

  const question = `[[mock:jitter=150]] ${LONG_QUESTION} fin-${uid()}`;
  const text = await chat(page, question, 30_000);

  expect(text).toContain(`MOCK-ECHO: ${question}`);
});
