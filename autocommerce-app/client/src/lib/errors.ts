/**
 * Normalisation des erreurs API en messages affichables.
 *
 * FastAPI / Pydantic renvoie `detail` sous plusieurs formes :
 *  - string            → ex. « Lot non trouvé »
 *  - array d'objets    → ex. erreur 422 : [{ type, loc, msg, input, ctx }, ...]
 *  - objet { message } → certains endpoints personnalisés
 *
 * Passer un tableau d'objets directement à `toast.error()` faisait planter
 * React (erreur #31 : « Objects are not valid as a React child »).
 */

type AnyRecord = Record<string, unknown>;

interface PydanticErrorItem {
  msg?: unknown;
  loc?: unknown;
  type?: unknown;
  ctx?: unknown;
  input?: unknown;
}

export function extractErrorMessage(
  err: unknown,
  fallback = 'Une erreur est survenue'
): string {
  const e = (typeof err === 'object' && err !== null ? err : {}) as AnyRecord;
  const response = e.response as AnyRecord | undefined;
  const data = response?.data;

  // Detail peut être présent soit à la racine de `data`, soit dans data.detail.
  let raw: unknown = data;
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    raw = (data as AnyRecord).detail ?? data;
  }

  // 1) string simple
  if (typeof raw === 'string' && raw.trim()) {
    return raw.trim();
  }

  // 2) tableau d'erreurs Pydantic (422)
  if (Array.isArray(raw)) {
    const parts = raw
      .map((item): string | null => {
        if (typeof item === 'string' && item.trim()) return item.trim();
        if (item && typeof item === 'object') {
          const obj = item as PydanticErrorItem;
          if (typeof obj.msg === 'string' && obj.msg.trim()) {
            const loc = Array.isArray(obj.loc)
              ? obj.loc.filter((x): x is string => typeof x === 'string').join('.')
              : '';
            return loc ? `${loc} : ${obj.msg}` : obj.msg.trim();
          }
        }
        return null;
      })
      .filter((x): x is string => x !== null);

    if (parts.length) {
      return parts.join(' · ');
    }
  }

  // 3) objet { message } / { msg }
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as AnyRecord;
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message.trim();
    if (typeof obj.msg === 'string' && obj.msg.trim()) return obj.msg.trim();
  }

  // 4) erreur réseau / Axios
  if (typeof (e as AnyRecord).message === 'string' && String((e as AnyRecord).message).trim()) {
    return String((e as AnyRecord).message).trim();
  }

  return fallback;
}

/** Normalise une saisie décimale (virgule → point, supprime les espaces). */
export function parseDecimalInput(value: string): number {
  return Number(String(value ?? '').trim().replace(/\s/g, '').replace(',', '.'));
}

export default extractErrorMessage;
