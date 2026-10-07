export const STOCK_STATUS_STYLES = {
  healthy: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  low: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  out_of_stock: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  overstock: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
};

export const SEVERITY_STYLES = {
  critical: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  high: 'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  medium: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  low: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  info: 'bg-brand-50 text-brand-700 ring-1 ring-brand-200',
};

export const URGENCY_STYLES = {
  critical: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  high: 'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  medium: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  low: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  none: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
};

export const MOVEMENT_STYLES = {
  fast_moving: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  medium_moving: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
  slow_moving: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  no_movement: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
};

/** Palette used across every chart so colours stay consistent. */
export const CHART_COLORS = [
  '#3366ff',
  '#00b8a9',
  '#f6a609',
  '#ef4444',
  '#8b5cf6',
  '#ec4899',
  '#14b8a6',
  '#f97316',
  '#6366f1',
  '#84cc16',
  '#06b6d4',
  '#a855f7',
];

export const PAYMENT_METHODS = ['cash', 'card', 'upi', 'credit'];

export const DATE_PRESETS = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
  { label: 'Last 365 days', days: 365 },
];
