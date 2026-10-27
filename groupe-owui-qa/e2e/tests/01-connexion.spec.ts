import { test, expect } from '../fixtures/owui';
import { AUTH, CHAT } from '../helpers/selectors';

test.describe('Connexion', () => {
  test('un utilisateur connecté arrive sur la page de chat', async ({ page }) => {
    await page.goto('/');

    // Pas de redirection vers la page de login : la session a été reprise.
    await expect(page).not.toHaveURL(/\/auth/);
    await expect(page.locator(CHAT.input)).toBeVisible();
  });

  test.describe('sans session', () => {
    // Navigateur vierge : on ignore la session sauvegardée par le setup.
    test.use({ storageState: { cookies: [], origins: [] } });

    test('un mauvais mot de passe affiche une erreur et reste sur /auth', async ({ page, tempUser }) => {
      await page.goto('/auth');
      await page.locator(AUTH.emailInput).fill(tempUser.email);
      await page.locator(AUTH.passwordInput).fill('mauvais-mot-de-passe');
      await page.locator(AUTH.submitButton).click();

      // Open WebUI affiche l'erreur du backend dans une notification (toast).
      await expect(page.locator('[data-sonner-toast]')).toContainText(/incorrect/i);
      await expect(page).toHaveURL(/\/auth/);
      await expect(page.locator(CHAT.input)).toHaveCount(0);
    });

    test('un utilisateur standard se connecte via le formulaire', async ({ page, tempUser }) => {
      await page.goto('/auth');
      await page.locator(AUTH.emailInput).fill(tempUser.email);
      await page.locator(AUTH.passwordInput).fill(tempUser.password);
      await page.locator(AUTH.submitButton).click();

      await expect(page.locator(CHAT.input)).toBeVisible({ timeout: 30_000 });
      await expect(page).not.toHaveURL(/\/auth/);
    });
  });
});
