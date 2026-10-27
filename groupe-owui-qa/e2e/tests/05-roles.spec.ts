/**
 * Contrôle d'accès : un utilisateur standard n'a pas accès à l'administration.
 */
import { test, expect, auth } from '../fixtures/owui';
import { AUTH, CHAT } from '../helpers/selectors';

test.describe('Rôles', () => {
  test('l\'API d\'administration refuse un utilisateur standard', async ({ request, tenantA, tempUser }) => {
    const asUser = await request.get(`${tenantA.url}/api/v1/users/`, { headers: auth(tempUser.token) });
    expect(asUser.status()).toBe(401);

    // Contrôle : la même requête passe pour l'admin (le refus vient bien du rôle).
    const asAdmin = await request.get(`${tenantA.url}/api/v1/users/`, { headers: auth(tenantA.token) });
    expect(asAdmin.ok()).toBeTruthy();
  });

  test.describe('dans le navigateur', () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test('un utilisateur standard est redirigé hors de /admin', async ({ page, tempUser }) => {
      await page.goto('/auth');
      await page.locator(AUTH.emailInput).fill(tempUser.email);
      await page.locator(AUTH.passwordInput).fill(tempUser.password);
      await page.locator(AUTH.submitButton).click();
      await expect(page.locator(CHAT.input)).toBeVisible({ timeout: 30_000 });

      await page.goto('/admin/users');
      await expect(page).not.toHaveURL(/\/admin/, { timeout: 15_000 });
    });
  });
});
