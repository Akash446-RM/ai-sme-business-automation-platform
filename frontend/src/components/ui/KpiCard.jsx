import { Minus, TrendingDown, TrendingUp } from 'lucide-react';
import { Skeleton } from './index';

/** A single headline metric with an optional period-over-period change. */
export function KpiCard({ label, value, change, hint, icon: Icon, tone = 'default', loading }) {
  if (loading) {
    return (
      <div className="card p-5">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-3 h-7 w-32" />
        <Skeleton className="mt-3 h-3 w-20" />
      </div>
    );
  }

  const tones = {
    default: 'bg-brand-50 text-brand-600',
    success: 'bg-emerald-50 text-emerald-600',
    warning: 'bg-amber-50 text-amber-600',
    danger: 'bg-red-50 text-red-600',
  };

  const hasChange = change !== null && change !== undefined;
  const positive = hasChange && change > 0;
  const negative = hasChange && change < 0;
  const ChangeIcon = positive ? TrendingUp : negative ? TrendingDown : Minus;

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-2 truncate text-2xl font-semibold text-slate-900">{value}</p>
        </div>
        {Icon && (
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${tones[tone]}`}>
            <Icon className="h-4.5 w-4.5" aria-hidden />
          </span>
        )}
      </div>

      {(hasChange || hint) && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {hasChange && (
            <span
              className={`inline-flex items-center gap-1 font-medium ${
                positive ? 'text-emerald-600' : negative ? 'text-red-600' : 'text-slate-500'
              }`}
            >
              <ChangeIcon className="h-3.5 w-3.5" />
              {Math.abs(change).toFixed(1)}%
            </span>
          )}
          {hint && <span className="truncate text-slate-500">{hint}</span>}
        </div>
      )}
    </div>
  );
}
