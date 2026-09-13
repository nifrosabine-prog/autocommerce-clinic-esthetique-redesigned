import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { DEFAULT_CURRENCY, normalizeCurrency } from '@/lib/currency';

export interface ClinicCurrency {
  currency_code: string;
  currency_symbol: string;
}

export function useCurrency(): ClinicCurrency {
  const [currency, setCurrency] = useState<ClinicCurrency>(DEFAULT_CURRENCY);

  useEffect(() => {
    let active = true;
    api.get('/settings/currency')
      .then((response) => {
        if (active) setCurrency(normalizeCurrency(response.data));
      })
      .catch(() => {
        // Le fallback local est volontairement silencieux pour ne pas masquer les données métier.
      });
    return () => { active = false; };
  }, []);

  return currency;
}
