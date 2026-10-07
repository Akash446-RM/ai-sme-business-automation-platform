import { Check, RefreshCw, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { alertApi } from '../api/endpoints';
import { Badge, Card, EmptyState, ErrorState, Loading, PageHeader, Select } from '../components/ui';
import { Pagination } from '../components/ui/DataTable';
import { KpiCard } from '../components/ui/KpiCard';
import { useToast } from '../components/ui/Toast';
import { useApi, usePaginatedList } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { SEVERITY_STYLES } from '../utils/constants';
import { formatDate, humanise } from '../utils/format';

export default function Alerts() {
  const toast = useToast();
  const { isManager } = useAuth();

  const [status, setStatus] = useState('open');
  const [severity, setSeverity] = useState('');
  const [scanning, setScanning] = useState(false);

  const summary = useApi(() => alertApi.summary(), []);
  const filters = useMemo(
    () => ({ status, severity: severity || undefined }),
    [status, severity],
  );
  const list = usePaginatedList(alertApi.list, filters, 20);

  const runScan = async () => {
    setScanning(true);
    try {
      const result = await alertApi.scan(7);
      toast.success(
        `Scan complete: ${result.created} new, ${result.updated} updated, ` +
          `${result.auto_resolved} resolved.`,
      );
      list.reload();
      summary.reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setScanning(false);
    }
  };

  const updateStatus = async (alert, nextStatus) => {
    try {
      await alertApi.updateStatus(alert.id, nextStatus);
      toast.success(`Alert ${nextStatus}.`);
      list.reload();
      summary.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Situations the automation engine detected in your business."
        actions={
          isManager && (
            <button type="button" className="btn-primary" onClick={runScan} disabled={scanning}>
              <RefreshCw className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} />
              {scanning ? 'Scanning…' : 'Run scan'}
            </button>
          )
        }
      />

      {summary.data && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <KpiCard label="Open alerts" value={summary.data.total_open} />
          <KpiCard label="Critical" value={summary.data.critical} tone="danger" />
          <KpiCard label="High" value={summary.data.high} tone="warning" />
          <KpiCard label="Medium" value={summary.data.medium} tone="warning" />
        </div>
      )}

      <Card className="mt-6" bodyClassName="p-0">
        <div className="flex flex-col gap-3 border-b border-surface-border p-4 sm:flex-row">
          <Select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            options={[
              { value: 'open', label: 'Open' },
              { value: 'acknowledged', label: 'Acknowledged' },
              { value: 'resolved', label: 'Resolved' },
              { value: 'all', label: 'All statuses' },
            ]}
          />
          <Select
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            placeholder="All severities"
            options={[
              { value: 'critical', label: 'Critical' },
              { value: 'high', label: 'High' },
              { value: 'medium', label: 'Medium' },
              { value: 'low', label: 'Low' },
              { value: 'info', label: 'Info' },
            ]}
          />
        </div>

        {list.loading ? (
          <Loading />
        ) : list.error ? (
          <ErrorState message={list.error} onRetry={list.reload} />
        ) : !list.items.length ? (
          <EmptyState
            title="No alerts"
            message={
              status === 'open'
                ? 'Nothing needs your attention right now. Run a scan to re-check.'
                : 'No alerts match this filter.'
            }
          />
        ) : (
          <ul className="divide-y divide-surface-border">
            {list.items.map((alert) => (
              <li key={alert.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <Badge className={SEVERITY_STYLES[alert.severity]}>
                        {humanise(alert.severity)}
                      </Badge>
                      <Badge className="bg-slate-100 text-slate-600">
                        {humanise(alert.alert_type)}
                      </Badge>
                      {alert.status !== 'open' && (
                        <Badge className="bg-slate-100 text-slate-500">
                          {humanise(alert.status)}
                        </Badge>
                      )}
                      <span className="text-xs text-slate-400">
                        {formatDate(alert.created_at, { withTime: true })}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-slate-900">{alert.title}</p>
                    <p className="mt-1 text-sm text-slate-600">{alert.description}</p>
                    {alert.recommended_action && (
                      <p className="mt-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
                        <strong>Recommended:</strong> {alert.recommended_action}
                      </p>
                    )}
                  </div>

                  {alert.status === 'open' && (
                    <div className="flex gap-1">
                      <button
                        type="button"
                        className="btn-secondary px-2 py-1.5 text-xs"
                        onClick={() => updateStatus(alert, 'acknowledged')}
                        title="Acknowledge"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="btn-secondary px-2 py-1.5 text-xs"
                        onClick={() => updateStatus(alert, 'dismissed')}
                        title="Dismiss"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        <Pagination
          page={list.page}
          totalPages={list.totalPages}
          total={list.total}
          pageSize={20}
          onChange={list.setPage}
        />
      </Card>
    </>
  );
}
