import {
  AlertTriangle,
  Boxes,
  IndianRupee,
  Info,
  Package,
  Receipt,
  TriangleAlert,
  Users,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { dashboardApi } from '../api/endpoints';
import { DonutChart, HorizontalBarChart, RevenueTrendChart } from '../components/charts';
import { Card, ErrorState, Loading, PageHeader } from '../components/ui';
import { KpiCard } from '../components/ui/KpiCard';
import { useApi } from '../hooks/useApi';
import { SEVERITY_STYLES } from '../utils/constants';
import { formatCurrency, formatDate, formatNumber } from '../utils/format';

const SEVERITY_ICONS = {
  critical: TriangleAlert,
  high: AlertTriangle,
  medium: AlertTriangle,
  info: Info,
};

export default function Dashboard() {
  const { data, loading, error, reload } = useApi(() => dashboardApi.summary(), []);

  if (loading) return <Loading label="Loading your business overview…" className="py-24" />;
  if (error) return <ErrorState message={error} onRetry={reload} className="py-24" />;

  const { kpis, revenue_trend: trend, top_products: topProducts, category_performance: categories,
          recent_sales: recentSales, insights } = data;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live view of sales, inventory and what needs your attention."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Revenue this month"
          value={formatCurrency(kpis.month_revenue)}
          change={kpis.month_growth_percent}
          hint="vs last month"
          icon={IndianRupee}
        />
        <KpiCard
          label="Today's sales"
          value={formatCurrency(kpis.today_revenue)}
          hint={`${kpis.today_transactions} transactions`}
          icon={Receipt}
          tone="success"
        />
        <KpiCard
          label="Average order value"
          value={formatCurrency(kpis.average_order_value)}
          hint={`${formatNumber(kpis.total_sales)} total sales`}
          icon={Users}
        />
        <KpiCard
          label="Inventory value"
          value={formatCurrency(kpis.inventory_value, { compact: true })}
          hint={`${kpis.active_products} active products`}
          icon={Boxes}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Low stock"
          value={formatNumber(kpis.low_stock_count)}
          hint="at or below reorder level"
          icon={AlertTriangle}
          tone="warning"
        />
        <KpiCard
          label="Out of stock"
          value={formatNumber(kpis.out_of_stock_count)}
          hint="cannot be sold"
          icon={Package}
          tone="danger"
        />
        <KpiCard
          label="Customers"
          value={formatNumber(kpis.total_customers)}
          icon={Users}
        />
        <KpiCard
          label="Open alerts"
          value={formatNumber(kpis.open_alerts)}
          hint="needing review"
          icon={TriangleAlert}
          tone={kpis.open_alerts > 0 ? 'warning' : 'success'}
        />
      </div>

      {/* Insights */}
      {insights?.length > 0 && (
        <Card
          title="What needs your attention"
          className="mt-6"
          action={
            <Link to="/alerts" className="text-xs font-medium text-brand-600 hover:underline">
              View all alerts
            </Link>
          }
          bodyClassName="divide-y divide-surface-border"
        >
          {insights.map((insight, index) => {
            const Icon = SEVERITY_ICONS[insight.severity] ?? Info;
            return (
              <div key={`${insight.type}-${index}`} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                <span
                  className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                    SEVERITY_STYLES[insight.severity] ?? SEVERITY_STYLES.info
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-slate-900">{insight.title}</p>
                    {insight.metric && (
                      <span className={`badge ${SEVERITY_STYLES[insight.severity] ?? ''}`}>
                        {insight.metric}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-sm text-slate-600">{insight.message}</p>
                </div>
              </div>
            );
          })}
        </Card>
      )}

      {/* Charts */}
      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="Revenue trend (last 30 days)" className="xl:col-span-2">
          <RevenueTrendChart data={trend} />
        </Card>
        <Card title="Revenue by category">
          <DonutChart
            data={categories.slice(0, 7).map((row) => ({
              category: row.category,
              revenue: Number(row.revenue),
            }))}
            nameKey="category"
            valueKey="revenue"
          />
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card
          title="Top products (last 30 days)"
          action={
            <Link to="/analytics" className="text-xs font-medium text-brand-600 hover:underline">
              Analytics
            </Link>
          }
        >
          <HorizontalBarChart
            data={topProducts.map((product) => ({
              name: product.name,
              revenue: Number(product.revenue),
            }))}
            xKey="revenue"
            yKey="name"
          />
        </Card>

        <Card
          title="Recent sales"
          action={
            <Link to="/sales" className="text-xs font-medium text-brand-600 hover:underline">
              All sales
            </Link>
          }
          bodyClassName="p-0"
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Bill</th>
                  <th>Customer</th>
                  <th>Date</th>
                  <th className="text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {recentSales.map((sale) => (
                  <tr key={sale.bill_no}>
                    <td className="font-mono text-xs">{sale.bill_no}</td>
                    <td className="max-w-[140px] truncate">{sale.customer_name ?? 'Walk-in'}</td>
                    <td className="whitespace-nowrap text-xs text-slate-500">
                      {formatDate(sale.sale_date, { withTime: true })}
                    </td>
                    <td className="text-right font-medium">
                      {formatCurrency(sale.total_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
