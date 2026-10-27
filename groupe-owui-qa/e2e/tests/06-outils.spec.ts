import { test, expect, MOCK_LLM_URL, MODEL, uid } from '../fixtures/owui';
import { CHAT } from '../helpers/selectors';
import { sendMessage, startNewChat, selectModel } from '../helpers/chat';

test('un outil sélectionné dans le chat est réellement exécuté', async ({ page, request, qaTool, tenantA }) => {
  const runId = `tool-${uid()}`;
  let chatId: string | undefined;

  try {
    await startNewChat(page);
    await selectModel(page, MODEL);

    await page.locator(CHAT.integrationsButton).click();
    await page.getByRole('button', { name: /^Outils \d+$/ }).click();
    const toolToggle = page.getByRole('button', { name: qaTool.name, exact: true });
    await expect(toolToggle).toBeVisible();
    await toolToggle.click();
    await expect(toolToggle).toHaveAttribute('aria-pressed', 'true');

    await sendMessage(page, `[[mock:tool=${runId}]] Exécute l'outil de vérification avec cet identifiant.`);

    const assistant = page.locator(CHAT.assistantMessage).last();
    await expect(assistant.locator('#response-content-container'))
      .toContainText(`MOCK-TOOL-RESULT: QA_TOOL_EXECUTED:${runId}`, { timeout: 30_000 });

    await expect.poll(async () => {
      const response = await request.get(`${MOCK_LLM_URL}/test/tool-invocations/${runId}`);
      if (!response.ok()) return -1;
      const receipt = await response.json();
      return receipt.calls;
    }, { timeout: 10_000 }).toBe(1);

    const match = page.url().match(/\/c\/([\w-]+)/);
    chatId = match?.[1];
  } finally {
    const match = page.url().match(/\/c\/([\w-]+)/);
    chatId ??= match?.[1];

    if (chatId) {
      const response = await request.delete(`${tenantA.url}/api/v1/chats/${chatId}`, {
        headers: { Authorization: `Bearer ${tenantA.token}` },
      });
      if (!response.ok() && response.status() !== 404) {
        throw new Error(`Suppression de la conversation de test impossible (${response.status()})`);
      }
    }

    const cleanup = await request.delete(`${MOCK_LLM_URL}/test/tool-invocations/${runId}`);
    if (!cleanup.ok()) {
      throw new Error(`Nettoyage du reçu d’invocation impossible (${cleanup.status()})`);
    }
  }
});
