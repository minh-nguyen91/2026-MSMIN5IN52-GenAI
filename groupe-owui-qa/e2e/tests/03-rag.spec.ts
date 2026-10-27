/**
 * Parcours RAG : un document est indexé dans une base de connaissances,
 * puis une question posée avec cette base doit s'appuyer sur ce document.
 * La préparation passe par une fixture API isolée ; les scénarios valident
 * aussi la réponse, la sélection et la citation dans l'interface.
 */
import { test, expect, MODEL, RAG_FACT, auth } from '../fixtures/owui';
import { CHAT } from '../helpers/selectors';
import { sendMessage, startNewChat, selectModel } from '../helpers/chat';

test.describe('RAG', () => {
  test('une question avec la base de connaissances renvoie le document source', async ({ request, tenantA, knowledgeBase }) => {
    const res = await request.post(`${tenantA.url}/api/chat/completions`, {
      headers: auth(tenantA.token),
      data: {
        model: MODEL, stream: false,
        messages: [{ role: 'user', content: 'Quelle est la capitale de Zorblandia ?' }],
        files: [{ type: 'collection', id: knowledgeBase.id }],
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();

    // Citation traçable : la source renvoyée est bien notre document.
    expect(body.sources?.[0]?.document?.join(' ')).toContain('Quetzalville');
    expect(body.sources?.[0]?.metadata?.[0]?.name).toBe(knowledgeBase.fileName);
    // Le contexte a bien été injecté dans le prompt (le mock le signale).
    expect(body.choices[0].message.content).toContain(`MOCK-RAG: ${RAG_FACT}`);
    expect(body.choices[0].message.content).toMatch(/fondée sur \d+ source/);
  });

  test('la base de connaissances apparaît dans l\'espace de travail', async ({ page, knowledgeBase }) => {
    await page.goto('/workspace/knowledge');
    await expect(page.getByText(knowledgeBase.name)).toBeVisible({ timeout: 15_000 });
  });

  test('une question depuis le chat affiche la réponse et la source de la connaissance', async ({ page, knowledgeBase }) => {
    await startNewChat(page);
    await selectModel(page, MODEL);

    await page.locator(CHAT.attachmentsButton).click();
    await page.getByRole('button', { name: /Joindre une connaissance/ }).click();
    await page.getByRole('button', { name: knowledgeBase.name, exact: true }).click();

    await sendMessage(page, 'Quelle est la capitale secrète de Zorblandia ?');

    const assistant = page.locator(CHAT.assistantMessage).last();
    await expect(assistant.locator('#response-content-container'))
      .toContainText(`MOCK-RAG: ${RAG_FACT}`, { timeout: 30_000 });
    await expect(assistant.getByRole('button', {
      name: `Voir la source : ${knowledgeBase.fileName}`,
    })).toBeVisible();
  });
});
