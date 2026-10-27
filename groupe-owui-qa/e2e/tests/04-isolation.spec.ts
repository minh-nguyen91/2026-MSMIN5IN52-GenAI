/**
 * Isolation multi-tenant (entre instances) et entre utilisateurs (même instance).
 */
import { test, expect, MODEL, uid, auth } from '../fixtures/owui';

test.describe('Isolation', () => {
  test('un jeton du tenant A est refusé par le tenant B', async ({ request, tenantA, tenantB }) => {
    const res = await request.get(`${tenantB.url}/api/v1/auths/`, { headers: auth(tenantA.token) });
    expect(res.status()).toBe(401);
  });

  test('une base de connaissances du tenant A est invisible depuis le tenant B', async ({ request, tenantA, tenantB }) => {
    const name = `secret-a-${uid()}`;
    const kb = await (await request.post(`${tenantA.url}/api/v1/knowledge/create`, {
      headers: auth(tenantA.token), data: { name, description: 'isolation' },
    })).json();

    try {
      const listB = await request.get(`${tenantB.url}/api/v1/knowledge/`, { headers: auth(tenantB.token) });
      expect(listB.ok()).toBeTruthy();
      expect(JSON.stringify(await listB.json())).not.toContain(name);
      // Même avec l'identifiant exact, B ne trouve rien.
      const direct = await request.get(`${tenantB.url}/api/v1/knowledge/${kb.id}`, { headers: auth(tenantB.token) });
      expect(direct.ok()).toBeFalsy();
    } finally {
      await request.delete(`${tenantA.url}/api/v1/knowledge/${kb.id}/delete`, { headers: auth(tenantA.token) });
    }
  });

  test('un utilisateur ne peut pas lire la conversation d\'un autre', async ({ request, tenantA, tempUser }) => {
    // L'admin crée une conversation privée...
    const chat = await (await request.post(`${tenantA.url}/api/v1/chats/new`, {
      headers: auth(tenantA.token),
      data: { chat: { title: `privé-${uid()}`, models: [MODEL], messages: [{ role: 'user', content: 'confidentiel' }] } },
    })).json();

    try {
      // ...que l'utilisateur standard ne peut ni lire ni lister.
      const read = await request.get(`${tenantA.url}/api/v1/chats/${chat.id}`, { headers: auth(tempUser.token) });
      expect(read.ok()).toBeFalsy();
      const list = await request.get(`${tenantA.url}/api/v1/chats/`, { headers: auth(tempUser.token) });
      expect(JSON.stringify(await list.json())).not.toContain(chat.id);
    } finally {
      await request.delete(`${tenantA.url}/api/v1/chats/${chat.id}`, { headers: auth(tenantA.token) });
    }
  });
});
