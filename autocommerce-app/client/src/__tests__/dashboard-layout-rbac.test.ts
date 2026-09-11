import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '@/components/layout/DashboardLayout';

function findNavigationItem(href: string) {
  return NAV_GROUPS
    .flatMap((group) => group.items)
    .find((item) => item.href === href);
}

describe('DashboardLayout RBAC navigation', () => {
  it('does not expose the CRM relationship copilot to roles rejected by its API', () => {
    expect(findNavigationItem('/copilote-crm')?.roles).toEqual(['directrice', 'medecin', 'admin']);
  });

  it('aligns social messaging visibility with the authorised reception roles', () => {
    expect(findNavigationItem('/social')?.roles).toEqual([
      'directrice',
      'assistante',
      'commercial',
      'admin',
    ]);
  });

  it('keeps loyalty visible only for roles accepted by the loyalty routes', () => {
    expect(findNavigationItem('/loyalty')?.roles).toEqual(['directrice', 'assistante', 'admin']);
  });
});
