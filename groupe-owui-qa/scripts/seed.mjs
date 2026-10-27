/**
 * Crée le compte admin (premier inscrit) sur les deux tenants, avec les
 * identifiants de .env. Idempotent : ne fait rien si le compte existe déjà.
 *
 *   npm run seed
 */
const email = process.env.OWUI_EMAIL;
const password = process.env.OWUI_PASSWORD;
const tenants = [
  { name: 'A', url: process.env.OWUI_URL || 'http://localhost:3000' },
  { name: 'B', url: process.env.OWUI_TENANT2_URL || 'http://localhost:3001' },
];

if (!email || !password) {
  console.error('OWUI_EMAIL / OWUI_PASSWORD manquants dans .env');
  process.exit(1);
}

async function post(url, path, body) {
  const res = await fetch(`${url}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { ok: res.ok, status: res.status, data: await res.json().catch(() => null) };
}

for (const t of tenants) {
  let res = await post(t.url, '/api/v1/auths/signin', { email, password });
  let action = 'déjà présent';
  if (!res.ok) {
    res = await post(t.url, '/api/v1/auths/signup', { name: `Admin ${t.name}`, email, password });
    action = 'créé';
  }
  if (!res.ok) throw new Error(`Tenant ${t.name} : échec (${res.status}) ${JSON.stringify(res.data)}`);
  if (res.data.role !== 'admin') throw new Error(`Tenant ${t.name} : ${email} n'est pas admin`);
  console.log(`Tenant ${t.name} (${t.url}) : admin ${action}`);
}
