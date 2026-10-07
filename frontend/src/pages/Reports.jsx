import { Download, FileBarChart } from 'lucide-react';
import { useMemo, useState } from 'react';
import { reportApi } from '../api/endpoints';
import { DonutChart, RevenueTrendChart, VerticalBarChart } from '../components/charts';
import { Badge, Card, EmptyState, ErrorState, Loading, PageHeader, Select } from '../components/ui';
import { KpiCard } from '../components/ui/KpiCard';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { URGENCY_STYLES } from '../utils/constants';
import { dateRange, formatCurrency, formatDate, formatNumber, humanise } from '../utils/format';

const REPORTS = [
  { id: 'business_summary', label: 'Business summary', loader: reportApi.businessSummary },
  { id: 'sales', label: 'Sales report', loader: reportApi.sales },
  { id: 'revenue', label: 'Revenue report', loader: reportApi.revenue },
  { id: 'products', label: 'Product performance', loader: reportApi.products },
  { id: 'customers', label: 'Customer report', loader: reportApi.customers },
  { id: 'inventory', label: 'Inventory report', loader: reportApi.inventory },
];

export default function Reports() {
  const toast = useToast();
  const [reportId, setReportId] = useState('business_summary');
  const [days, setDays] = useState(30);

  const report = REPORTS.find((item) => item.id === reportId);
  const range = useMemo(() => (reportId === 'inventory' ? {} : dateRange(days)), [days, reportId]);
  const state = useApi(() => report.loader(range), [reportId, days]);

  const download = () => {
    if (!state.data) return;
    const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${reportId}-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success('Report exported.');
  };

  return (
    <>
      <PageHeader
        title="Reports"
        description="Filterable business reports built from the same figures as your dashboard."
        actions={
          <>
            <Select
              value={reportId}
              onChange={(event) => setReportId(event.target.value)}
              options={REPORTS.map((item) => ({ value: item.id, label: item.label }))}
            />
            {reportId !== 'inventory' && (
              <Select
                value={String(days)}
                onChange={(event) => setDays(Number(event.target.value))}
                options={[
                  { value: '7', label: 'Last 7 days' },
                  { value: '30', label: 'Last 30 days' },
                  { value: '90', label: 'Last 90 days' },
                  { value: '365', label: 'Last 365 days' },
                ]}
              />
            )}
            <button type="button" className="btn-secondary" onClick={download} disabled={!state.data}>
              <Download className="h-4 w-4" />
              Export
            </button>
          </>
        }
      />

      {state.loading ? (
        <Loading label="Generating report…" className="py-20" />
      ) : state.error ? (
        <ErrorState message={state.error} onRetry={state.reload} />
      ) : !state.data ? (
        <EmptyState title="No report data" />
      ) : (
        <>
          <Card className="mb-4">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <span className="flex items-center gap-2 font-medium text-slate-900">
                <FileBarChart className="h-4 w-4 text-brand-600" />
                {state.data.meta.title}
              </span>
              <span className="text-slate-500">
                Period: {formatDate(state.data.meta.date_from)} – {formatDate(state.data.meta.date_to)}
              </span>
              <span className="text-slate-500">
                Generated {formatDate(state.data.meta.generated_at, { withTime: true })}
              </span>
            </div>
          </Card>

          {reportId === 'business_summary' && <BusinessSummary data={state.data} />}
          {reportId === 'sales' && <SalesReport data={state.data} />}
          {reportId === 'revenue' && <RevenueReport data={state.data} />}
          {reportId === 'products' && <ProductReport data={state.data} />}
          {reportId === 'customers' && <CustomerReport data={state.data} />}
          {reportId === 'inventory' && <InventoryReport data={state.data} />}
        </>
      )}
    </>
  );
}

/* ------------------------------------------------------------- summaries */

function BusinessSummary({ data }) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Revenue"
          value={formatCurrency(data.revenue)}
          change={data.revenue_growth_percent}
        />
        <KpiCard
          label="Gross profit"
          value={formatCurrency(data.gross_profit)}
          hint={`${data.gross_margin_percent}% margin`}
        />
        <KpiCard label="Transactions" value={formatNumber(data.transactions)} />
        <KpiCard label="Active customers" value={formatNumber(data.active_customers)} />
      </div>

      <Card title="Key findings" className="mt-4">
        <ul className="space-y-2">
          {data.headline_findings.map((finding, index) => (
            <li key={index} className="flex gap-2 text-sm text-slate-700">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
              {finding}
            </li>
          ))}
        </ul>
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SimpleTable
          title="Top products"
          columns={['Product', 'Units', 'Revenue']}
          rows={data.top_products.map((row) => [
            row.name,
            formatNumber(row.units_sold),
            formatCurrency(row.revenue),
          ])}
        />
        <SimpleTable
          title="Top categories"
          columns={['Category', 'Revenue', 'Share']}
          rows={data.top_categories.map((row) => [
            row.category,
            formatCurrency(row.revenue),
            `${row.revenue_share_percent.toFixed(1)}%`,
          ])}
        />
        <SimpleTable
          title="Sales leaderboard"
          columns={['Employee', 'Sales', 'Revenue']}
          rows={data.employee_leaderboard.map((row) => [
            row.name,
            formatNumber(row.transactions),
            formatCurrency(row.revenue),
          ])}
        />
        <Card title="Inventory position">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Stat label="Inventory value" value={formatCurrency(data.inventory_value)} />
            <Stat label="Low stock" value={formatNumber(data.low_stock_count)} />
            <Stat label="Out of stock" value={formatNumber(data.out_of_stock_count)} />
            <Stat label="Open alerts" value={formatNumber(data.open_alerts)} />
          </dl>
        </Card>
      </div>
    </>
  );
}

function SalesReport({ data }) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Revenue"
          value={formatCurrency(data.total_revenue)}
          change={data.revenue_growth_percent}
        />
        <KpiCard label="Transactions" value={formatNumber(data.total_transactions)} />
        <KpiCard label="Units sold" value={formatNumber(data.total_units)} />
        <KpiCard
          label="Gross profit"
          value={formatCurrency(data.gross_profit)}
          hint={`${data.gross_margin_percent}% margin`}
        />
      </div>
      <Card title="Daily revenue" className="mt-4">
        <RevenueTrendChart data={data.daily_breakdown} height={300} />
      </Card>
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Payment mix">
          <DonutChart
            data={data.payment_mix.map((row) => ({
              method: humanise(row.payment_method),
              revenue: Number(row.revenue),
            }))}
            nameKey="method"
            valueKey="revenue"
          />
        </Card>
        <SimpleTable
          title="Payment breakdown"
          columns={['Method', 'Transactions', 'Revenue', 'Share']}
          rows={data.payment_mix.map((row) => [
            humanise(row.payment_method),
            formatNumber(row.transactions),
            formatCurrency(row.revenue),
            `${row.share_percent.toFixed(1)}%`,
          ])}
        />
      </div>
    </>
  );
}

function RevenueReport({ data }) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard label="Total revenue" value={formatCurrency(data.total_revenue)} />
        <KpiCard label="Gross profit" value={formatCurrency(data.total_gross_profit)} />
        <KpiCard
          label="Best month"
          value={data.best_month?.period ?? '—'}
          hint={data.best_month ? formatCurrency(data.best_month.revenue) : undefined}
        />
      </div>
      <Card title="Monthly revenue" className="mt-4">
        <VerticalBarChart
          data={data.monthly_breakdown.map((row) => ({
            period: row.period,
            revenue: Number(row.revenue),
          }))}
          xKey="period"
          yKey="revenue"
          height={300}
          name="Revenue"
        />
      </Card>
      <SimpleTable
        className="mt-4"
        title="Category breakdown"
        columns={['Category', 'Units', 'Revenue', 'Gross profit', 'Share']}
        rows={data.category_breakdown.map((row) => [
          row.category,
          formatNumber(row.units_sold),
          formatCurrency(row.revenue),
          formatCurrency(row.gross_profit),
          `${row.revenue_share_percent.toFixed(1)}%`,
        ])}
      />
    </>
  );
}

function ProductReport({ data }) {
  return (
    <div className="grid grid-cols-1 gap-4">
      <SimpleTable
        title="Best performers"
        columns={['Product', 'Category', 'Units', 'Revenue', 'Gross profit']}
        rows={data.best_performers.map((row) => [
          row.name,
          row.category,
          formatNumber(row.units_sold),
          formatCurrency(row.revenue),
          formatCurrency(row.gross_profit),
        ])}
      />
      <SimpleTable
        title="Worst performers"
        columns={['Product', 'Category', 'Units', 'Revenue', 'Stock']}
        rows={data.worst_performers.map((row) => [
          row.name,
          row.category,
          formatNumber(row.units_sold),
          formatCurrency(row.revenue),
          formatNumber(row.current_stock),
        ])}
      />
    </div>
  );
}

function CustomerReport({ data }) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Active customers" value={formatNumber(data.total_active_customers)} />
        <KpiCard label="Repeat customers" value={formatNumber(data.repeat_customer_count)} />
        <KpiCard label="Repeat rate" value={`${data.repeat_rate_percent}%`} />
        <KpiCard label="Average value" value={formatCurrency(data.average_customer_value)} />
      </div>
      <SimpleTable
        className="mt-4"
        title="Top customers"
        columns={['Customer', 'City', 'Orders', 'Spend', 'Share']}
        rows={data.top_customers.map((row) => [
          row.name,
          row.city ?? '—',
          formatNumber(row.total_orders),
          formatCurrency(row.total_spent),
          `${row.revenue_share_percent.toFixed(1)}%`,
        ])}
      />
    </>
  );
}

function InventoryReport({ data }) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard label="Products" value={formatNumber(data.total_products)} />
        <KpiCard label="Units on hand" value={formatNumber(data.total_units)} />
        <KpiCard label="Stock value" value={formatCurrency(data.total_stock_value)} />
      </div>

      <Card title="Reorder recommendations" className="mt-4" bodyClassName="p-0">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="text-right">Stock</th>
                <th className="text-right">Forecast</th>
                <th className="text-right">Order</th>
                <th className="text-right">Cost</th>
                <th>Urgency</th>
              </tr>
            </thead>
            <tbody>
              {data.reorder_recommendations.map((row) => (
                <tr key={row.product_id}>
                  <td className="font-medium text-slate-900">{row.name}</td>
                  <td className="text-right">{row.current_stock}</td>
                  <td className="text-right">{row.forecast_demand.toFixed(0)}</td>
                  <td className="text-right font-semibold">{row.recommended_quantity}</td>
                  <td className="text-right">{formatCurrency(row.estimated_cost)}</td>
                  <td>
                    <Badge className={URGENCY_STYLES[row.urgency]}>{humanise(row.urgency)}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <SimpleTable
        className="mt-4"
        title="Valuation by category"
        columns={['Category', 'Products', 'Units', 'Cost value', 'Retail value']}
        rows={data.valuation_by_category.map((row) => [
          row.category,
          formatNumber(row.product_count),
          formatNumber(row.total_units),
          formatCurrency(row.cost_value),
          formatCurrency(row.retail_value),
        ])}
      />
    </>
  );
}

/* --------------------------------------------------------------- helpers */

function SimpleTable({ title, columns, rows, className = '' }) {
  return (
    <Card title={title} className={className} bodyClassName="p-0">
      {!rows.length ? (
        <EmptyState title="No data" className="py-8" />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                {columns.map((column, index) => (
                  <th key={column} className={index > 0 ? 'text-right' : undefined}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td
                      key={cellIndex}
                      className={
                        cellIndex === 0 ? 'font-medium text-slate-900' : 'text-right'
                      }
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
