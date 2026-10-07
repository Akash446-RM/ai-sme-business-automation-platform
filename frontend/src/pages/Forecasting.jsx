import { AlertTriangle, Brain, CircleCheck, Info, TrendingUp } from 'lucide-react';
import { useMemo, useState } from 'react';
import { forecastApi, productApi } from '../api/endpoints';
import { ForecastChart, VerticalBarChart } from '../components/charts';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  Select,
} from '../components/ui';
import { KpiCard } from '../components/ui/KpiCard';
import { useApi, useDebounced } from '../hooks/useApi';
import { URGENCY_STYLES } from '../utils/constants';
import { formatCurrency, formatDate, formatNumber, humanise } from '../utils/format';

const HORIZONS = [
  { value: '7', label: 'Next 7 days' },
  { value: '14', label: 'Next 14 days' },
  { value: '30', label: 'Next 30 days' },
];

export default function Forecasting() {
  const [horizon, setHorizon] = useState(7);
  const status = useApi(() => forecastApi.status(), []);
  const sales = useApi(() => forecastApi.sales(horizon), [horizon]);
  const risk = useApi(
    () => forecastApi.demandSummary({ horizon_days: horizon, limit: 20 }),
    [horizon],
  );

  const trained = status.data?.sales_model_trained;

  return (
    <>
      <PageHeader
        title="Forecasting"
        description="What the models expect to happen next, and what it means for your stock."
        actions={
          <Select
            value={String(horizon)}
            onChange={(event) => setHorizon(Number(event.target.value))}
            options={HORIZONS}
          />
        }
      />

      <ModelStatus state={status} />

      {trained === false ? (
        <Card className="mt-4">
          <EmptyState
            title="No forecasting model has been trained yet"
            message="Run 'python -m app.scripts.train_models' in the backend to train the sales and demand models from your history. Until then, reorder advice falls back to recent sales velocity."
          />
        </Card>
      ) : (
        <>
          <SalesForecast state={sales} horizon={horizon} />
          <StockRisk state={risk} horizon={horizon} />
        </>
      )}

      <ProductForecast horizon={horizon} />
    </>
  );
}

/* ------------------------------------------------------------ model card */

function ModelStatus({ state }) {
  if (state.loading) return <Loading className="py-8" />;
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;

  const { sales_model: salesModel, demand_model: demandModel } = state.data;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ModelCard title="Sales forecasting model" model={salesModel} unit="currency" />
      <ModelCard title="Demand forecasting model" model={demandModel} unit="units" />
    </div>
  );
}

function ModelCard({ title, model, unit }) {
  if (!model) {
    return (
      <Card title={title}>
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Info className="h-4 w-4" />
          Not trained yet.
        </p>
      </Card>
    );
  }

  const metrics = model.metrics?.test_metrics ?? {};
  const improvement = model.metrics?.improvement_over_best_baseline ?? {};
  const baselineName = model.metrics?.best_baseline;
  const beatsBaseline = (improvement.mae_improvement_percent ?? 0) > 0;

  return (
    <Card
      title={title}
      action={
        <Badge
          className={
            beatsBaseline
              ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
              : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
          }
        >
          {beatsBaseline ? (
            <CircleCheck className="mr-1 h-3 w-3" />
          ) : (
            <AlertTriangle className="mr-1 h-3 w-3" />
          )}
          {beatsBaseline ? 'Beats baseline' : 'Review needed'}
        </Badge>
      }
    >
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Metric label="Algorithm" value={model.algorithm} />
        <Metric
          label="Average error"
          value={
            unit === 'currency'
              ? formatCurrency(metrics.mae)
              : `${Number(metrics.mae ?? 0).toFixed(2)} units/day`
          }
        />
        <Metric
          label={unit === 'currency' ? 'MAPE' : 'sMAPE'}
          value={`${unit === 'currency' ? metrics.mape ?? '—' : metrics.smape ?? '—'}%`}
        />
        <Metric label="R²" value={metrics.r2 ?? '—'} />
      </dl>

      <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
        Measured on {formatNumber(metrics.n)} unseen days. Beats the best simple baseline
        ({humanise(baselineName ?? '')}) by{' '}
        <strong className="text-slate-900">
          {improvement.mae_improvement_percent ?? 0}%
        </strong>{' '}
        on mean absolute error. Trained {formatDate(model.trained_at)}.
      </p>
    </Card>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 truncate font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

/* --------------------------------------------------------- sales forecast */

function SalesForecast({ state, horizon }) {
  if (state.loading) return <Loading className="py-16" />;
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (!state.data) return null;

  const data = state.data;

  // Join history and forecast onto one continuous series for the chart.
  const chartData = [
    ...data.history.slice(-30).map((row) => ({
      date: row.date,
      actual: row.revenue,
      predicted: null,
    })),
    ...data.predictions.map((row) => ({
      date: row.date,
      actual: null,
      predicted: row.predicted_revenue,
    })),
  ];
  // Bridge the gap so the two lines connect visually.
  if (chartData.length > data.predictions.length) {
    const lastActualIndex = chartData.length - data.predictions.length - 1;
    chartData[lastActualIndex].predicted = chartData[lastActualIndex].actual;
  }

  return (
    <>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard
          label={`Forecast revenue (${horizon} days)`}
          value={formatCurrency(data.total_predicted_revenue)}
          icon={TrendingUp}
        />
        <KpiCard
          label="Forecast daily average"
          value={formatCurrency(data.daily_average_predicted)}
          change={data.change_vs_recent_percent}
          hint="vs recent actual average"
        />
        <KpiCard
          label="Recent daily average"
          value={formatCurrency(data.recent_daily_average)}
          hint="last 30 days actual"
        />
      </div>

      <Card title="Revenue: history and forecast" className="mt-4">
        <ForecastChart data={chartData} height={320} />
        <p className="mt-3 text-xs text-slate-500">
          The dashed line is the model's prediction. Typical error is about{' '}
          {formatCurrency(data.model.test_mae)} per day, so treat each point as a range rather
          than an exact figure.
        </p>
      </Card>
    </>
  );
}

/* ------------------------------------------------------------ stock risk */

function StockRisk({ state, horizon }) {
  if (state.loading) return <Loading className="py-12" />;
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (!state.data?.items?.length) {
    return (
      <Card title="Inventory implications" className="mt-4">
        <EmptyState
          title="No stock risk detected"
          message={`Every product has enough stock for its forecast demand over the next ${horizon} days.`}
        />
      </Card>
    );
  }

  const { items, at_risk_count: atRisk } = state.data;

  return (
    <Card
      title={`Inventory implications (next ${horizon} days)`}
      className="mt-4"
      action={
        <span className="text-xs text-slate-500">
          <strong className="text-red-600">{atRisk}</strong> products at high risk
        </span>
      }
      bodyClassName="p-0"
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th className="text-right">Stock</th>
              <th className="text-right">Forecast demand</th>
              <th className="text-right">Cover</th>
              <th className="text-right">Suggested order</th>
              <th>Urgency</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.product_id}>
                <td>
                  <p className="font-medium text-slate-900">{item.name}</p>
                  <p className="font-mono text-xs text-slate-500">{item.sku}</p>
                </td>
                <td className="text-right">{item.current_stock}</td>
                <td
                  className={`text-right ${
                    item.forecast_demand > item.current_stock ? 'font-semibold text-red-600' : ''
                  }`}
                >
                  {item.forecast_demand.toFixed(0)}
                </td>
                <td className="text-right">
                  {item.days_of_cover !== null ? `${item.days_of_cover.toFixed(0)}d` : '—'}
                </td>
                <td className="text-right font-semibold">{item.recommended_quantity}</td>
                <td>
                  <Badge className={URGENCY_STYLES[item.urgency]}>{humanise(item.urgency)}</Badge>
                </td>
                <td className="text-xs text-slate-500">
                  {item.forecast_source === 'ml_demand_model' ? (
                    <span className="inline-flex items-center gap-1 text-brand-700">
                      <Brain className="h-3 w-3" /> ML model
                    </span>
                  ) : (
                    'Sales velocity'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* --------------------------------------------------- per product forecast */

function ProductForecast({ horizon }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const debounced = useDebounced(query, 300);

  const { data: matches } = useApi(
    () => (debounced.length >= 2 ? productApi.search(debounced, 8) : Promise.resolve([])),
    [debounced],
  );

  const forecast = useApi(
    () => forecastApi.demand(selected.id, horizon),
    [selected?.id, horizon],
    { skip: !selected },
  );

  const chartData = useMemo(() => {
    if (!forecast.data) return [];
    return [
      ...forecast.data.history.slice(-30).map((row) => ({
        date: row.date,
        actual: row.units,
        predicted: null,
      })),
      ...forecast.data.predictions.map((row) => ({
        date: row.date,
        actual: null,
        predicted: row.predicted_units,
      })),
    ];
  }, [forecast.data]);

  return (
    <Card title="Forecast demand for a specific product" className="mt-4">
      <div className="relative max-w-md">
        <input
          className="input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search for a product…"
        />
        {matches?.length > 0 && query.length >= 2 && !selected && (
          <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-surface-border bg-white shadow-raised">
            {matches.map((product) => (
              <li key={product.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                  onClick={() => {
                    setSelected(product);
                    setQuery(product.name);
                  }}
                >
                  <span className="block font-medium text-slate-900">{product.name}</span>
                  <span className="font-mono text-xs text-slate-500">{product.sku}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {selected && (
          <button
            type="button"
            className="mt-2 text-xs text-brand-600 hover:underline"
            onClick={() => {
              setSelected(null);
              setQuery('');
            }}
          >
            Clear selection
          </button>
        )}
      </div>

      {selected && (
        <div className="mt-4">
          {forecast.loading ? (
            <Loading />
          ) : forecast.error ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {forecast.error}
            </div>
          ) : forecast.data ? (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric label="Current stock" value={formatNumber(forecast.data.current_stock)} />
                <Metric
                  label={`Forecast demand (${horizon}d)`}
                  value={`${forecast.data.total_predicted_units.toFixed(0)} units`}
                />
                <Metric
                  label="Expected stock after"
                  value={`${forecast.data.expected_stock_after_horizon.toFixed(0)} units`}
                />
                <Metric
                  label="Stockout expected"
                  value={forecast.data.stockout_expected ? 'Yes' : 'No'}
                />
              </div>
              <div className="mt-4">
                <ForecastChart data={chartData} height={260} />
              </div>
              {forecast.data.stockout_expected && (
                <p className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  Forecast demand of {forecast.data.total_predicted_units.toFixed(0)} units exceeds
                  the {forecast.data.current_stock} units in stock. Reorder before this product
                  runs out.
                </p>
              )}
            </>
          ) : null}
        </div>
      )}
    </Card>
  );
}
