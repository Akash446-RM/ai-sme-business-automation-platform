import { AlertTriangle, Boxes, PackageX, RefreshCw, TrendingDown } from 'lucide-react';
import { useMemo, useState } from 'react';
import { inventoryApi } from '../api/endpoints';
import { DataTable, Pagination, SearchInput } from '../components/ui/DataTable';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeader,
  Select,
} from '../components/ui';
import { KpiCard } from '../components/ui/KpiCard';
import { useToast } from '../components/ui/Toast';
import { useApi, useDebounced, usePaginatedList } from '../hooks/useApi';
import { MOVEMENT_STYLES, STOCK_STATUS_STYLES, URGENCY_STYLES } from '../utils/constants';
import { formatCurrency, formatDate, formatNumber, humanise } from '../utils/format';

const TABS = [
  { id: 'stock', label: 'Stock levels' },
  { id: 'recommendations', label: 'Reorder recommendations' },
  { id: 'movement', label: 'Movement analysis' },
  { id: 'ledger', label: 'Transaction ledger' },
];

export default function Inventory() {
  const [tab, setTab] = useState('stock');
  const { data: overview, loading, error, reload } = useApi(() => inventoryApi.overview(), []);

  return (
    <>
      <PageHeader
        title="Inventory"
        description="Stock health, demand-aware reorder advice and the full movement ledger."
      />

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((index) => (
            <KpiCard key={index} loading />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Stock value"
            value={formatCurrency(overview.total_stock_value, { compact: true })}
            hint={`${formatNumber(overview.total_units)} units on hand`}
            icon={Boxes}
          />
          <KpiCard
            label="Low stock"
            value={formatNumber(overview.low_stock_count)}
            hint="at or below reorder level"
            icon={AlertTriangle}
            tone="warning"
          />
          <KpiCard
            label="Out of stock"
            value={formatNumber(overview.out_of_stock_count)}
            hint="unavailable to sell"
            icon={PackageX}
            tone="danger"
          />
          <KpiCard
            label="Dead stock"
            value={formatNumber(overview.dead_stock_count)}
            hint="no sales in 90 days"
            icon={TrendingDown}
            tone="warning"
          />
        </div>
      )}

      <div className="mt-6 flex gap-1 overflow-x-auto border-b border-surface-border">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === item.id
                ? 'border-brand-600 text-brand-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {tab === 'stock' && <StockTab />}
        {tab === 'recommendations' && <RecommendationsTab />}
        {tab === 'movement' && <MovementTab />}
        {tab === 'ledger' && <LedgerTab />}
      </div>
    </>
  );
}

/* -------------------------------------------------------------- stock tab */

function StockTab() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const debouncedSearch = useDebounced(search);

  const filters = useMemo(
    () => ({ search: debouncedSearch || undefined, status: status || undefined }),
    [debouncedSearch, status],
  );
  const list = usePaginatedList(inventoryApi.stock, filters, 15);

  const columns = [
    {
      key: 'name',
      header: 'Product',
      render: (row) => (
        <div>
          <p className="font-medium text-slate-900">{row.name}</p>
          <p className="font-mono text-xs text-slate-500">{row.sku}</p>
        </div>
      ),
    },
    { key: 'category', header: 'Category' },
    { key: 'stock', header: 'Stock', align: 'right', render: (row) => formatNumber(row.stock) },
    { key: 'reorder_level', header: 'Reorder at', align: 'right' },
    {
      key: 'units_sold_30d',
      header: 'Sold (30d)',
      align: 'right',
      render: (row) => (
        <div>
          <p>{formatNumber(row.units_sold_30d)}</p>
          <p className="text-xs text-slate-500">{row.daily_velocity}/day</p>
        </div>
      ),
    },
    {
      key: 'days_of_cover',
      header: 'Cover',
      align: 'right',
      render: (row) =>
        row.days_of_cover !== null ? `${row.days_of_cover.toFixed(0)} days` : '—',
    },
    {
      key: 'movement_class',
      header: 'Movement',
      render: (row) => (
        <Badge className={MOVEMENT_STYLES[row.movement_class]}>
          {humanise(row.movement_class)}
        </Badge>
      ),
    },
    {
      key: 'stock_status',
      header: 'Status',
      render: (row) => (
        <Badge className={STOCK_STATUS_STYLES[row.stock_status]}>
          {humanise(row.stock_status)}
        </Badge>
      ),
    },
  ];

  return (
    <Card bodyClassName="p-0">
      <div className="flex flex-col gap-3 border-b border-surface-border p-4 sm:flex-row">
        <SearchInput value={search} onChange={setSearch} placeholder="Search products…" className="sm:max-w-sm" />
        <Select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          placeholder="All stock states"
          options={[
            { value: 'healthy', label: 'Healthy' },
            { value: 'low', label: 'Low stock' },
            { value: 'out_of_stock', label: 'Out of stock' },
            { value: 'overstock', label: 'Overstock' },
          ]}
        />
      </div>
      <DataTable
        columns={columns}
        rows={list.items}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        emptyTitle="No products match"
      />
      <Pagination
        page={list.page}
        totalPages={list.totalPages}
        total={list.total}
        pageSize={15}
        onChange={list.setPage}
      />
    </Card>
  );
}

/* --------------------------------------------------- recommendations tab */

function RecommendationsTab() {
  const [horizon, setHorizon] = useState(7);
  const [selected, setSelected] = useState(null);
  const { data, loading, error, reload } = useApi(
    () => inventoryApi.recommendations({ horizon_days: horizon, limit: 50 }),
    [horizon],
  );

  const totalCost = (data ?? []).reduce((sum, item) => sum + Number(item.estimated_cost), 0);

  return (
    <>
      <Card
        title={`Reorder recommendations (${horizon}-day horizon)`}
        action={
          <div className="flex items-center gap-2">
            <Select
              value={String(horizon)}
              onChange={(event) => setHorizon(Number(event.target.value))}
              options={[
                { value: '7', label: '7 days' },
                { value: '14', label: '14 days' },
                { value: '30', label: '30 days' },
              ]}
            />
            <button type="button" className="btn-secondary" onClick={reload}>
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        }
        bodyClassName="p-0"
      >
        {loading ? (
          <Loading label="Calculating demand-aware recommendations…" />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : !data?.length ? (
          <EmptyState
            title="Nothing needs reordering"
            message={`Every product has enough stock to cover forecast demand for the next ${horizon} days.`}
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border bg-slate-50 px-5 py-3 text-sm">
              <span className="text-slate-600">
                <strong className="text-slate-900">{data.length}</strong> products to reorder
              </span>
              <span className="text-slate-600">
                Estimated cost <strong className="text-slate-900">{formatCurrency(totalCost)}</strong>
              </span>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="text-right">Stock</th>
                    <th className="text-right">Forecast demand</th>
                    <th className="text-right">Safety stock</th>
                    <th className="text-right">Order qty</th>
                    <th className="text-right">Est. cost</th>
                    <th>Urgency</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.map((item) => (
                    <tr key={item.product_id}>
                      <td>
                        <p className="font-medium text-slate-900">{item.name}</p>
                        <p className="font-mono text-xs text-slate-500">{item.sku}</p>
                      </td>
                      <td className="text-right">{item.current_stock}</td>
                      <td className="text-right">
                        <p>{item.forecast_demand.toFixed(0)}</p>
                        <p className="text-xs text-slate-500">
                          {item.forecast_source === 'ml_demand_model' ? 'ML model' : 'velocity'}
                        </p>
                      </td>
                      <td className="text-right">{item.safety_stock.toFixed(0)}</td>
                      <td className="text-right text-base font-semibold text-slate-900">
                        {item.recommended_quantity}
                      </td>
                      <td className="text-right">{formatCurrency(item.estimated_cost)}</td>
                      <td>
                        <Badge className={URGENCY_STYLES[item.urgency]}>
                          {humanise(item.urgency)}
                        </Badge>
                      </td>
                      <td className="text-right">
                        <button
                          type="button"
                          className="btn-ghost px-2 py-1 text-xs"
                          onClick={() => setSelected(item)}
                        >
                          Why?
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Modal
        open={Boolean(selected)}
        title={selected ? `Why reorder ${selected.name}?` : ''}
        onClose={() => setSelected(null)}
        width="max-w-xl"
      >
        {selected && (
          <div className="space-y-4">
            <div className="rounded-lg bg-brand-50 px-4 py-3">
              <p className="text-sm text-brand-900">
                Recommended order:{' '}
                <strong className="text-base">{selected.recommended_quantity} units</strong> —
                estimated cost {formatCurrency(selected.estimated_cost)}
              </p>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Reasoning
              </p>
              <ul className="space-y-1.5">
                {selected.reasons.map((reason, index) => (
                  <li key={index} className="flex gap-2 text-sm text-slate-700">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-500" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Evidence
              </p>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(selected.evidence)
                  .filter(([key]) => key !== 'formula')
                  .map(([key, value]) => (
                    <div key={key} className="rounded bg-slate-50 px-3 py-2">
                      <dt className="text-xs text-slate-500">{humanise(key)}</dt>
                      <dd className="font-medium text-slate-900">{String(value ?? '—')}</dd>
                    </div>
                  ))}
              </dl>
              <p className="mt-2 rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100">
                {selected.evidence.formula}
              </p>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

/* ----------------------------------------------------------- movement tab */

function MovementTab() {
  const { data, loading, error, reload } = useApi(
    () => inventoryApi.movement({ window_days: 30, limit: 10 }),
    [],
  );
  const { data: valuation } = useApi(() => inventoryApi.valuation(), []);

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <MovementList title="Fast moving (last 30 days)" items={data.fast_moving} showRevenue />
      <MovementList title="Slow moving (last 30 days)" items={data.slow_moving} showRevenue />
      <MovementList title="Never sold" items={data.never_sold} />
      <Card title="Stock value by category" bodyClassName="p-0">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th className="text-right">Products</th>
                <th className="text-right">Units</th>
                <th className="text-right">Cost value</th>
                <th className="text-right">Potential margin</th>
              </tr>
            </thead>
            <tbody>
              {(valuation ?? []).map((row) => (
                <tr key={row.category}>
                  <td className="font-medium text-slate-900">{row.category}</td>
                  <td className="text-right">{row.product_count}</td>
                  <td className="text-right">{formatNumber(row.total_units)}</td>
                  <td className="text-right">{formatCurrency(row.cost_value)}</td>
                  <td className="text-right text-emerald-700">
                    {formatCurrency(row.potential_margin)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function MovementList({ title, items, showRevenue }) {
  return (
    <Card title={title} bodyClassName="p-0">
      {!items?.length ? (
        <EmptyState title="No products in this group" className="py-8" />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="text-right">Stock</th>
                <th className="text-right">Units sold</th>
                {showRevenue && <th className="text-right">Revenue</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.product_id}>
                  <td>
                    <p className="font-medium text-slate-900">{item.name}</p>
                    <p className="text-xs text-slate-500">{item.category}</p>
                  </td>
                  <td className="text-right">{formatNumber(item.stock)}</td>
                  <td className="text-right">{formatNumber(item.units_sold)}</td>
                  {showRevenue && (
                    <td className="text-right">{formatCurrency(item.revenue)}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------- ledger tab */

function LedgerTab() {
  const [type, setType] = useState('');
  const filters = useMemo(() => ({ transaction_type: type || undefined }), [type]);
  const list = usePaginatedList(inventoryApi.transactions, filters, 20);

  const columns = [
    {
      key: 'created_at',
      header: 'When',
      render: (row) => (
        <span className="whitespace-nowrap text-xs">
          {formatDate(row.created_at, { withTime: true })}
        </span>
      ),
    },
    {
      key: 'product_name',
      header: 'Product',
      render: (row) => (
        <div>
          <p className="font-medium text-slate-900">{row.product_name ?? `#${row.product_id}`}</p>
          <p className="font-mono text-xs text-slate-500">{row.product_sku}</p>
        </div>
      ),
    },
    {
      key: 'transaction_type',
      header: 'Type',
      render: (row) => (
        <Badge className="bg-slate-100 text-slate-600">{humanise(row.transaction_type)}</Badge>
      ),
    },
    {
      key: 'quantity',
      header: 'Change',
      align: 'right',
      render: (row) => (
        <span className={row.quantity < 0 ? 'font-medium text-red-600' : 'font-medium text-emerald-700'}>
          {row.quantity > 0 ? '+' : ''}
          {row.quantity}
        </span>
      ),
    },
    {
      key: 'stock',
      header: 'Stock after',
      align: 'right',
      render: (row) => (
        <span className="text-slate-600">
          {row.previous_stock} → <strong className="text-slate-900">{row.new_stock}</strong>
        </span>
      ),
    },
    {
      key: 'reference',
      header: 'Reference',
      render: (row) => <span className="font-mono text-xs">{row.reference ?? '—'}</span>,
    },
  ];

  return (
    <Card bodyClassName="p-0">
      <div className="border-b border-surface-border p-4">
        <Select
          value={type}
          onChange={(event) => setType(event.target.value)}
          placeholder="All movement types"
          options={[
            { value: 'sale', label: 'Sale' },
            { value: 'purchase', label: 'Purchase' },
            { value: 'adjustment', label: 'Adjustment' },
            { value: 'return', label: 'Return' },
            { value: 'initial', label: 'Opening stock' },
          ]}
          className="sm:max-w-xs"
        />
      </div>
      <DataTable
        columns={columns}
        rows={list.items}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        emptyTitle="No stock movements recorded"
      />
      <Pagination
        page={list.page}
        totalPages={list.totalPages}
        total={list.total}
        pageSize={20}
        onChange={list.setPage}
      />
    </Card>
  );
}
