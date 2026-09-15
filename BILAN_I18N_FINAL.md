# Bilan final — Couverture i18n AutoCommerce Clinic

## Périmètre

Les neuf composants ciblés ont été entièrement migrés vers `react-i18next` : `PatientFormDialog`, `SignaturePad`, `SimulationCrayonPad`, `PointageWidget`, `LinaChatWidget`, `BarcodeCameraScanner`, `ConsommableForm`, `ConsommablesList` et `InjectableAssignmentSelector`. Les chaînes utilisateur résiduelles de `LandingPage.tsx` ont également été externalisées.

## Contrôles

| Contrôle | Résultat |
|---|---:|
| Parité récursive des locales fr/en/de/it/ar | PASS — 1 964 clés par langue |
| Clés `componentUi` | PASS — 212 par langue |
| Références statiques `t()` | PASS — 219 résolues |
| Paramètres d’interpolation | PASS — aucune divergence |
| Textes codés en dur signalés | PASS — aucun résidu impératif |
| `pnpm check` | PASS |
| `pnpm test` | PASS — 13 fichiers, 73 tests |
| `pnpm build` | PASS |
| `dist/public/index.html` | PRESENT |

Les textes métier dynamiques, noms propres et données provenant de l’API restent dynamiques. Les formats de date/heure utilisent la langue i18n résolue.
