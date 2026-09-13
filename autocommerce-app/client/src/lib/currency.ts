export interface CurrencyDisplay {
  currency_code: string;
  currency_symbol: string;
}

export const DEFAULT_CURRENCY: CurrencyDisplay = { currency_code: 'TND', currency_symbol: 'DT' };

export function normalizeCurrency(value: Partial<CurrencyDisplay> | null | undefined): CurrencyDisplay {
  const currency_code = String(value?.currency_code || DEFAULT_CURRENCY.currency_code).trim().toUpperCase();
  const currency_symbol = String(value?.currency_symbol || DEFAULT_CURRENCY.currency_symbol).trim();
  return {
    currency_code: /^[A-Z]{3}$/.test(currency_code) ? currency_code : DEFAULT_CURRENCY.currency_code,
    currency_symbol: currency_symbol || DEFAULT_CURRENCY.currency_symbol,
  };
}

export function formatMoney(amount: number | string | null | undefined, currency: CurrencyDisplay, decimals = 3): string {
  const numericAmount = Number(amount ?? 0);
  const safeAmount = Number.isFinite(numericAmount) ? numericAmount : 0;
  return `${safeAmount.toFixed(decimals)} ${currency.currency_symbol}`;
}

/**
 * Une facture est un document historique : sa devise enregistrée prime toujours
 * sur la devise courante de la clinique. Aucun taux de change n'est appliqué ici.
 */
export function getInvoiceCurrency(
  invoice: Partial<CurrencyDisplay> | null | undefined,
  currentCurrency: CurrencyDisplay,
): CurrencyDisplay {
  if (invoice?.currency_code || invoice?.currency_symbol) {
    return normalizeCurrency({
      currency_code: invoice.currency_code,
      currency_symbol: invoice.currency_symbol,
    });
  }
  return currentCurrency;
}
