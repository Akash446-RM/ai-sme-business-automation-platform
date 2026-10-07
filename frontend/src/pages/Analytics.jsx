import { useMemo, useState } from 'react';
import { analyticsApi } from '../api/endpoints';
import {
  DonutChart,
  HorizontalBarChart,
  RevenueTrendChart,
  VerticalBarChart,
} from '../components/charts';
import { Badge, Card, EmptyState, ErrorState, Loading, PageHeader, Select } from '../components/ui';
import { KpiCard } from '../components/ui/KpiCard';
import { useApi } from '../hooks/useApi';
import { DATE_PRESETS } from '../utils/constants';
import { dateRange, formatCurrency, formatNumber, formatPercent, humanise } from '../utils/format';

export default function Analytics() {
  const [days, setDays] = useState(30);
  const [granularity, setGranularity] = useState('day');
  const range = useMemo(() => dateRange(days), [days]);

  const summary = useApi(() => analyticsApi.summary(range), [days]);
  const trend = useApi(() => analyticsApi.salesTrend({ ...range, granularity }), [days, granularity]);
  const products = useApi(() => analyticsApi.products({ ...range, limit: 10 }), [days]);
  const worst = useApi(() => analyticsApi.products({ ...range, limit: 5, order: 'bottom' }), [days]);
  const categories = useApi(() => analyticsApi.categories(range), [days]);
  const customers = useApi(() => analyticsApi.customers({ ...range, limit: 8 }), [days]);
  const employees = useApi(() => analyticsApi.employees({ ...range, limit: 6 }), [days]);
  const payments = useApi(() => analyticsApi.paymentMix(range), [days]);
  const weekday = useApi(() => analyticsApi.weekdayPattern(range), [days]);
  const hourly = useApi(() => analyticsApi.hourlyPattern(range), [days]);

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Sales, revenue, product, category and customer performance."
        actions={
          <Select
            value={String(days)}
            onChange={(event) => setDays(Number(event.target.value))}
            options={DATE_PRESETS.map((preset) => ({
              value: String(preset.days),
              label: preset.label,
            }))}
          />
        }
      />

      {/* Headline metrics */}
      {summary.loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <KpiCard key={i} loading />
          ))}
        </div>
      ) : summary.error ? (
        <ErrorState message={summary.error} onRetry={summary.reload} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Revenue"
            value={formatCurrency(summary.data.revenue)}
            change={summary.data.revenue_growth_percent}
            hint="vs previous period"
          />
          <KpiCard
            label="Transactions"
            value={formatNumber(summary.data.transactions)}
            change={summary.data.transaction_growth_percent}
          />
          <KpiCard label="Units sold" value={formatNumber(summary.data.units_sold)} />
          <KpiCard
            label="Average order value"
            value={formatCurrency(summary.data.average_order_value)}
          />
        </div>
      )}

      {/* Trend */}
      <Card
        title="Revenue over time"
        className="mt-6"
        action={
          <Select
            value={granularity}
            onChange={(event) => setGranularity(event.target.value)}
            options={[
              { value: 'day', label: 'Daily' },
              { value: 'week', label: 'Weekly' },
              { value: 'month', label: 'Monthly' },
            ]}
          />
        }
      >
        <ChartPanel state={trend}>
          {(data) => <RevenueTrendChart data={data.points} height={300} />}
        </ChartPanel>
      </Card>

      {/* Products and categories */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Top products by revenue">
          <ChartPanel state={products}>
            {(data) => (
              <HorizontalBarChart
                data={data.map((row) => ({ name: row.name, revenue: Number(row.revenue) }))}
                xKey="revenue"
                yKey="name"
                height={340}
              />
            )}
          </ChartPanel>
        </Card>

        <Card title="Revenue by category">
          <ChartPanel state={categories}>
            {(data) => (
              <DonutChart
                data={data.slice(0, 8).map((row) => ({
                  category: row.category,
                  revenue: Number(row.revenue),
                }))}
                nameKey="category"
                valueKey="revenue"
                height={340}
              />
            )}
          </ChartPanel>
        </Card>
      </div>

      {/* Product detail table */}
      <Card title="Product performance" className="mt-4" bodyClassName="p-0">
        <ChartPanel state={products}>
          {(data) => (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Category</th>
                    <th className="text-right">Units</th>
                    <th className="text-right">Revenue</th>
                    <th className="text-right">Gross profit</th>
                    <th className="text-right">Share</th>
                    <th className="text-right">Growth</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row) => (
                    <tr key={row.product_id}>
                      <td className="font-medium text-slate-900">{row.name}</td>
                      <td>{row.category}</td>
                      <td className="text-right">{formatNumber(row.units_sold)}</td>
                      <td className="text-right font-medium">{formatCurrency(row.revenue)}</td>
                      <td className="text-right text-emerald-700">
                        {formatCurrency(row.gross_profit)}
                      </td>
                      <td className="text-right">{row.revenue_share_percent.toFixed(1)}%</td>
                      <td className="text-right">
                        <GrowthBadge value={row.growth_percent} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </ChartPanel>
      </Card>

      {/* Category table + worst performers */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Category performance" bodyClassName="p-0">
          <ChartPanel state={categories}>
            {(data) => (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th className="text-right">Revenue</th>
                      <th className="text-right">Share</th>
                      <th className="text-right">Growth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((row) => (
                      <tr key={row.category}>
                        <td className="font-medium text-slate-900">{row.category}</td>
                        <td className="text-right">{formatCurrency(row.revenue)}</td>
                        <td className="text-right">{row.revenue_share_percent.toFixed(1)}%</td>
                        <td className="text-right">
                          <GrowthBadge value={row.growth_percent} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartPanel>
        </Card>

        <Card title="Lowest performing products" bodyClassName="p-0">
          <ChartPanel state={worst}>
            {(data) => (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th className="text-right">Units</th>
                      <th className="text-right">Revenue</th>
                      <th className="text-right">Stock</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((row) => (
                      <tr key={row.product_id}>
                        <td className="font-medium text-slate-900">{row.name}</td>
                        <td className="text-right">{formatNumber(row.units_sold)}</td>
                        <td className="text-right">{formatCurrency(row.revenue)}</td>
                        <td className="text-right">{formatNumber(row.current_stock)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartPanel>
        </Card>
      </div>

      {/* Customers and employees */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Top customers" bodyClassName="p-0">
          <ChartPanel state={customers}>
            {(data) => (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Customer</th>
                      <th className="text-right">Orders</th>
                      <th className="text-right">Spend</th>
                      <th className="text-right">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((row) => (
                      <tr key={row.customer_id}>
                        <td>
                          <p className="font-medium text-slate-900">{row.name}</p>
                          <p className="text-xs text-slate-500">{row.city ?? '—'}</p>
                        </td>
                        <td className="text-right">{row.total_orders}</td>
                        <td className="text-right font-medium">
                          {formatCurrency(row.total_spent)}
                        </td>
                        <td className="text-right">{row.revenue_share_percent.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartPanel>
        </Card>

        <Card title="Sales leaderboard" bodyClassName="p-0">
          <ChartPanel state={employees}>
            {(data) => (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th className="text-right">Sales</th>
                      <th className="text-right">Revenue</th>
                      <th className="text-right">Avg order</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((row) => (
                      <tr key={row.employee_id}>
                        <td>
                          <p className="font-medium text-slate-900">{row.name}</p>
                          <p className="text-xs text-slate-500">{row.role}</p>
                        </td>
                        <td className="text-right">{row.transactions}</td>
                        <td className="text-right font-medium">{formatCurrency(row.revenue)}</td>
                        <td className="text-right">{formatCurrency(row.average_order_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartPanel>
        </Card>
      </div>

      {/* Behaviour patterns */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="Sales by day of week">
          <ChartPanel state={weekday}>
            {(data) => (
              <VerticalBarChart
                data={data.map((row) => ({
                  day: row.weekday.slice(0, 3),
                  revenue: Number(row.revenue),
                }))}
                xKey="day"
                yKey="revenue"
                name="Revenue"
              />
            )}
          </ChartPanel>
        </Card>

        <Card title="Sales by hour">
          <ChartPanel state={hourly}>
            {(data) => (
              <VerticalBarChart
                data={data.map((row) => ({
                  hour: `${String(row.hour).padStart(2, '0')}:00`,
                  transactions: row.transactions,
                }))}
                xKey="hour"
                yKey="transactions"
                currency={false}
                name="Transactions"
              />
            )}
          </ChartPanel>
        </Card>

        <Card title="Payment mix">
          <ChartPanel state={payments}>
            {(data) => (
              <DonutChart
                data={data.map((row) => ({
                  method: humanise(row.payment_method),
                  revenue: Number(row.revenue),
                }))}
                nameKey="method"
                valueKey="revenue"
              />
            )}
          </ChartPanel>
        </Card>
      </div>
    </>
  );
}

function ChartPanel({ state, children }) {
  if (state.loading) return <Loading className="py-16" />;
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (!state.data || (Array.isArray(state.data) && state.data.length === 0)) {
    return <EmptyState title="No data for this period" className="py-16" />;
  }
  return children(state.data);
}

function GrowthBadge({ value }) {
  if (value === null || value === undefined) {
    return <span className="text-xs text-slate-400">new</span>;
  }
  const positive = value >= 0;
  return (
    <Badge className={positive ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}>
      {formatPercent(value)}
    </Badge>
  );
}
