/**
 * Fixtures partagées par les tests.
 *
 * - tenantA / tenantB : URL + jeton admin, obtenus UNE fois par worker
 *   (Open WebUI limite le débit de /api/v1/auths/signin).
 * - tempUser : utilisateur standard créé pour CE test (email unique) puis
 *   supprimé après, même si le test échoue. Aucun test ne dépend des données
 *   d'un autre : l'ordre d'exécution n'a pas d'importance.
 */
import { expect, test as base, type APIRequestContext } from '@playwright/test';

export interface Tenant {
  url: string;
  token: string;
}

export interface TempUser {
  id: string;
  email: string;
  password: string;
  token: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  fileName: string;
  fileId: string;
}

export interface QaTool {
  id: string;
  name: string;
}

export const MODEL = 'mock-echo';
export const RAG_FACT = 'La capitale secrète de Zorblandia est Quetzalville.';
export const MOCK_LLM_URL = process.env.MOCK_LLM_URL || 'http://localhost:11500';

/** Question longue (~25 mots) pour le scénario « streaming irrégulier » et sa baseline. */
export const LONG_QUESTION =
  'Peux-tu expliquer en quelques phrases comment fonctionne un test de bout en bout '
  + 'sur une application de chat qui répond en streaming avec un modèle de langage';

/** Identifiant unique pour nommer les données d'un test (users, KB, chats). */
export const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export async function signin(request: APIRequestContext, url: string, email: string, password: string) {
  const res = await request.post(`${url}/api/v1/auths/signin`, { data: { email, password } });
  if (!res.ok()) throw new Error(`Connexion impossible sur ${url} (${res.status()}) : ${await res.text()}`);
  return (await res.json()).token as string;
}

export const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

async function adminTenant(playwright: { request: { newContext: () => Promise<APIRequestContext> } }, url: string) {
  const ctx = await playwright.request.newContext();
  const token = await signin(ctx, url, process.env.OWUI_EMAIL!, process.env.OWUI_PASSWORD!);
  await ctx.dispose();
  return { url, token };
}

async function deleteKnowledgeResources(
  request: APIRequestContext,
  tenant: Tenant,
  knowledgeId: string | undefined,
  fileId: string | undefined,
) {
  const headers = auth(tenant.token);
  const errors: string[] = [];

  if (knowledgeId) {
    const response = await request.delete(`${tenant.url}/api/v1/knowledge/${knowledgeId}/delete`, { headers });
    if (!response.ok() && response.status() !== 404) {
      errors.push(`base ${knowledgeId} (${response.status()})`);
    }
  }
  if (fileId) {
    const response = await request.delete(`${tenant.url}/api/v1/files/${fileId}`, { headers });
    if (!response.ok() && response.status() !== 404) {
      errors.push(`fichier ${fileId} (${response.status()})`);
    }
  }

  if (errors.length > 0) {
    throw new Error(`Nettoyage des ressources RAG impossible : ${errors.join(', ')}`);
  }
}

async function createKnowledgeBase(
  request: APIRequestContext,
  tenant: Tenant,
  name: string,
): Promise<KnowledgeBase> {
  let knowledgeId: string | undefined;
  let fileId: string | undefined;
  const fileName = `${name}.txt`;

  try {
    const knowledgeResponse = await request.post(`${tenant.url}/api/v1/knowledge/create`, {
      headers: auth(tenant.token),
      data: { name, description: 'Base isolée créée par une fixture E2E' },
    });
    if (!knowledgeResponse.ok()) {
      throw new Error(`Création de la base RAG impossible (${knowledgeResponse.status()})`);
    }
    const knowledge = await knowledgeResponse.json();
    if (typeof knowledge.id !== 'string') {
      throw new Error('La réponse de création RAG ne contient pas d’identifiant');
    }
    knowledgeId = knowledge.id;

    const fileResponse = await request.post(`${tenant.url}/api/v1/files/?process=true`, {
      headers: auth(tenant.token),
      multipart: {
        file: { name: fileName, mimeType: 'text/plain', buffer: Buffer.from(RAG_FACT) },
      },
    });
    if (!fileResponse.ok()) {
      throw new Error(`Téléversement du document RAG impossible (${fileResponse.status()})`);
    }
    const file = await fileResponse.json();
    if (typeof file.id !== 'string') {
      throw new Error('La réponse du téléversement RAG ne contient pas d’identifiant');
    }
    fileId = file.id;

    await expect.poll(async () => {
      const response = await request.post(`${tenant.url}/api/v1/knowledge/${knowledgeId}/file/add`, {
        headers: auth(tenant.token),
        data: { file_id: fileId },
      });
      return response.status();
    }, { timeout: 20_000 }).toBe(200);

    if (!knowledgeId || !fileId) {
      throw new Error('La base ou le document RAG n’a pas été créé');
    }
    return { id: knowledgeId, name, fileName, fileId };
  } catch (error) {
    await deleteKnowledgeResources(request, tenant, knowledgeId, fileId);
    throw error;
  }
}

async function deleteQaTool(request: APIRequestContext, tenant: Tenant, toolId: string) {
  const response = await request.delete(`${tenant.url}/api/v1/tools/id/${toolId}/delete`, {
    headers: auth(tenant.token),
  });
  if (!response.ok() && response.status() !== 404) {
    throw new Error(`Suppression de l’outil E2E impossible (${response.status()})`);
  }
}

export const test = base.extend<
  { tempUser: TempUser; knowledgeBase: KnowledgeBase; qaTool: QaTool },
  { tenantA: Tenant; tenantB: Tenant }
>({
  tenantA: [async ({ playwright }, use) => {
    await use(await adminTenant(playwright, process.env.OWUI_URL || 'http://localhost:3000'));
  }, { scope: 'worker' }],

  tenantB: [async ({ playwright }, use) => {
    await use(await adminTenant(playwright, process.env.OWUI_TENANT2_URL || 'http://localhost:3001'));
  }, { scope: 'worker' }],

  tempUser: async ({ request, tenantA }, use) => {
    const email = `user-${uid()}@test.local`;
    const password = `Pw-${uid()}`;
    const res = await request.post(`${tenantA.url}/api/v1/auths/add`, {
      headers: auth(tenantA.token),
      data: { name: 'Utilisateur test', email, password, role: 'user' },
    });
    if (!res.ok()) throw new Error(`Création utilisateur impossible (${res.status()}) : ${await res.text()}`);
    const user = await res.json();

    await use({ id: user.id, email, password, token: user.token });

    // Nettoyage : supprime l'utilisateur (et ses données) quoi qu'il arrive.
    await request.delete(`${tenantA.url}/api/v1/users/${user.id}`, { headers: auth(tenantA.token) });
  },

  knowledgeBase: async ({ request, tenantA }, use) => {
    const name = `kb-${uid()}`;
    const resource = await createKnowledgeBase(request, tenantA, name);
    try {
      await use(resource);
    } finally {
      await deleteKnowledgeResources(request, tenantA, resource.id, resource.fileId);
    }
  },

  qaTool: async ({ request, tenantA }, use) => {
    const id = `f1_qa_${uid().replace(/-/g, '_')}`;
    const name = `F1 QA Tool ${uid()}`;
    const content = [
      '"""',
      'title: F1 QA invocation probe',
      'author: groupe-owui-qa',
      'version: 0.1.0',
      '"""',
      'import json',
      'from urllib.request import Request, urlopen',
      '',
      'class Tools:',
      '    async def record_qa_invocation(self, run_id: str) -> str:',
      '        """Record a deterministic F1 E2E tool invocation.',
      '        :param run_id: Unique identifier for this test run',
      '        :return: A marker proving that this function executed',
      '        """',
      '        payload = json.dumps({"run_id": run_id}).encode("utf-8")',
      '        request = Request(',
      '            "http://mock-llm:11500/test/tool-invocations",',
      '            data=payload,',
      '            headers={"Content-Type": "application/json"},',
      '            method="POST",',
      '        )',
      '        with urlopen(request, timeout=10) as response:',
      '            result = json.loads(response.read().decode("utf-8"))',
      '        if result.get("run_id") != run_id:',
      '            raise RuntimeError("Tool invocation receipt did not match")',
      '        return "QA_TOOL_EXECUTED:" + run_id',
    ].join('\n');

    const response = await request.post(`${tenantA.url}/api/v1/tools/create`, {
      headers: auth(tenantA.token),
      data: { id, name, content, meta: { description: 'Temporary deterministic E2E tool' } },
    });
    if (!response.ok()) {
      throw new Error(`Création de l’outil E2E impossible (${response.status()})`);
    }

    try {
      await use({ id, name });
    } finally {
      await deleteQaTool(request, tenantA, id);
    }
  },
});

export { expect } from '@playwright/test';
