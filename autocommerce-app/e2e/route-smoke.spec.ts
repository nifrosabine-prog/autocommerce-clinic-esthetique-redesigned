import { expect, test, type Page } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@clinic.local';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;

const routes = [
  '/',
  '/login',
  '/dashboard',
  '/dashboard-ia',
  '/workflows',
  '/copilote-crm',
  '/analytics',
  '/agenda',
  '/clinical-ops',
  '/patients',
  '/patients/1',
  '/stock',
  '/invoices',
  '/commissions',
  '/delegues',
  '/loyalty',
  '/teleconsultation/1',
  '/recruitment',
  '/social',
  '/equipe',
  '/settings',
  '/settings/actes',
  '/admin/equipe',
  '/admin/salles',
  '/admin/rh',
  '/404',
];

async function login(page: Page): Promise<void> {
  if (!ADMIN_PASSWORD) throw new Error('E2E_ADMIN_PASSWORD requis hors dépôt');
  await page.goto('/login');
  await expect(page.getByText('Connectez-vous à votre compte')).toBeVisible();
  const responsePromise = page.waitForResponse((response) => (
    response.url().includes('/auth/login') && response.request().method() === 'POST'
  ));
  await page.getByLabel('Identifiant').fill(ADMIN_EMAIL);
  await page.getByLabel('Mot de passe').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.access_token).toBeTruthy();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test('smoke utilisateur page par page — routes publiques et privées', async ({ page }) => {
  test.setTimeout(180_000);
  const pageErrors: string[] = [];
  const serverErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 500) serverErrors.push(`${response.status()} ${response.url()}`);
  });

  await page.goto('/');
  await expect(page.locator('body')).not.toContainText('Internal Server Error');
  await login(page);

  for (const route of routes.filter((item) => item !== '/' && item !== '/login')) {
    await page.goto(route, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
    await expect(page.locator('body')).not.toContainText('Application error');
    await expect(page.locator('body')).toBeVisible();
  }

  expect(serverErrors, `Réponses HTTP 5xx détectées:\n${serverErrors.join('\n')}`).toEqual([]);
  expect(pageErrors, `Erreurs JavaScript détectées:\n${pageErrors.join('\n')}`).toEqual([]);
});
