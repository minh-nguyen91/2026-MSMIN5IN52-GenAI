import { test, expect, MODEL, LONG_QUESTION, uid, auth } from '../fixtures/owui';
import { CHAT } from '../helpers/selectors';
import { startNewChat, selectModel, sendMessage } from '../helpers/chat';

test.describe('Chat', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, MODEL);
  });

  test('une question reçoit la réponse complète du modèle en streaming', async ({ page }) => {
    const marker = `bonjour-${uid()}`;
    await sendMessage(page, marker);

    // expect() réessaie jusqu'au timeout : le marqueur étant le DERNIER mot
    // streamé, sa présence complète prouve la fin du streaming.
    // (toContainText et non toHaveText : le conteneur inclut aussi le texte
    // caché de la barre d'actions « Demander / Expliquer ».)
    const answer = page.locator(CHAT.assistantMessage).last().locator('#response-content-container');
    await expect(answer).toContainText(`MOCK-ECHO: ${marker}`, { timeout: 30_000 });
  });

  test('une réponse longue au débit irrégulier est attendue jusqu\'au bout', async ({ page }) => {
    // Même scénario que la baseline naïve (e2e/baseline/) : le mock streame
    // ~25 mots avec un délai aléatoire entre chaque, comme un vrai LLM.
    const question = `[[mock:jitter=150]] ${LONG_QUESTION} fin-${uid()}`;
    await sendMessage(page, question);

    const answer = page.locator(CHAT.assistantMessage).last().locator('#response-content-container');
    await expect(answer).toContainText(`MOCK-ECHO: ${question}`, { timeout: 30_000 });
  });

  test('la conversation est enregistrée côté serveur', async ({ page, request, tenantA }) => {
    const marker = `persistance-${uid()}`;
    await sendMessage(page, marker);
    await expect(page.locator(CHAT.assistantMessage).last()).toContainText(`MOCK-ECHO: ${marker}`, { timeout: 30_000 });

    // L'URL passe à /c/<id> une fois le chat créé.
    await expect(page).toHaveURL(/\/c\/[\w-]+/);
    const chatId = page.url().split('/c/')[1];

    // Vérification par l'API : le chat existe et contient bien les deux messages.
    await expect.poll(async () => {
      const res = await request.get(`${tenantA.url}/api/v1/chats/${chatId}`, { headers: auth(tenantA.token) });
      return JSON.stringify(await res.json());
    }, { timeout: 10_000 }).toContain(`MOCK-ECHO: ${marker}`);

    await request.delete(`${tenantA.url}/api/v1/chats/${chatId}`, { headers: auth(tenantA.token) });
  });

  test('une panne du modèle est signalée à l\'utilisateur', async ({ page }) => {
    // [[mock:error]] fait répondre le LLM simulé en HTTP 500.
    await sendMessage(page, `[[mock:error]] ${uid()}`);

    // Pas de réponse inventée : un message d'erreur visible, et l'application reste utilisable.
    const last = page.locator(CHAT.assistantMessage).last();
    await expect(last).toContainText(/erreur|error/i, { timeout: 30_000 });
    await expect(last).not.toContainText('MOCK-ECHO');
    await expect(page.locator(CHAT.input)).toBeEditable();
  });
});
