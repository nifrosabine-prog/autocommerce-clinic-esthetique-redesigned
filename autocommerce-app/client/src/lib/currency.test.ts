import { describe, expect, it } from 'vitest';
import { formatMoney, getInvoiceCurrency, normalizeCurrency } from './currency';

describe('currency display rules', () => {
  const current = { currency_code: 'EUR', currency_symbol: '€' };

  it('keeps the historical invoice currency after a clinic currency change', () => {
    const historical = getInvoiceCurrency(
      { currency_code: 'TND', currency_symbol: 'DT' },
      current,
    );

    expect(formatMoney(180, historical)).toBe('180.000 DT');
    expect(historical.currency_code).toBe('TND');
  });

  it('uses the current clinic currency for a new operation without historical metadata', () => {
    expect(formatMoney(180, getInvoiceCurrency({}, current))).toBe('180.000 €');
  });

  it('does not convert amounts while formatting', () => {
    expect(formatMoney(180, { currency_code: 'EUR', currency_symbol: '€' })).toBe('180.000 €');
  });

  it('normalizes invalid or incomplete currency settings safely', () => {
    expect(normalizeCurrency({ currency_code: 'eur', currency_symbol: ' € ' })).toEqual({
      currency_code: 'EUR',
      currency_symbol: '€',
    });
    expect(normalizeCurrency({ currency_code: 'EURO', currency_symbol: '' })).toEqual({
      currency_code: 'TND',
      currency_symbol: 'DT',
    });
  });
});
