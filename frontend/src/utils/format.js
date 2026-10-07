const CURRENCY_SYMBOL = 'Rs.';

/** Format a monetary amount, optionally in compact form for chart axes. */
export function formatCurrency(value, { compact = false, decimals = 0 } = {}) {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return `${CURRENCY_SYMBOL} 0`;

  if (compact) {
    if (Math.abs(amount) >= 10000000) return `${CURRENCY_SYMBOL} ${(amount / 10000000).toFixed(2)}Cr`;
    if (Math.abs(amount) >= 100000) return `${CURRENCY_SYMBOL} ${(amount / 100000).toFixed(2)}L`;
    if (Math.abs(amount) >= 1000) return `${CURRENCY_SYMBOL} ${(amount / 1000).toFixed(1)}K`;
  }

  return `${CURRENCY_SYMBOL} ${amount.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function formatNumber(value, decimals = 0) {
  const number = Number(value ?? 0);
  if (Number.isNaN(number)) return '0';
  return number.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined) return '—';
  const number = Number(value);
  return `${number > 0 ? '+' : ''}${number.toFixed(decimals)}%`;
}

export function formatDate(value, { withTime = false } = {}) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const options = { day: '2-digit', month: 'short', year: 'numeric' };
  if (withTime) {
    options.hour = '2-digit';
    options.minute = '2-digit';
  }
  return date.toLocaleDateString('en-IN', options);
}

export function formatShortDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

/** Convert snake_case or kebab-case identifiers into readable labels. */
export function humanise(value) {
  if (!value) return '';
  return String(value)
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function toISODate(date) {
  return date.toISOString().slice(0, 10);
}

/** A [from, to] window ending today, expressed as ISO dates. */
export function dateRange(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - (days - 1));
  return { date_from: toISODate(from), date_to: toISODate(to) };
}
