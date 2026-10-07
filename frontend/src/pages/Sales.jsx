import { Eye, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { salesApi } from '../api/endpoints';
import NewSale from '../features/sales/NewSale';
import { DataTable, Pagination, SearchInput } from '../components/ui/DataTable';
import {
  Badge,
  Card,
  ConfirmDialog,
  Loading,
  Modal,
  PageHeader,
  Select,
} from '../components/ui';
import { useToast } from '../components/ui/Toast';
import { useApi, useDebounced, usePaginatedList } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { PAYMENT_METHODS } from '../utils/constants';
import { formatCurrency, formatDate, humanise } from '../utils/format';

export default function Sales() {
  const toast = useToast();
  const { isManager } = useAuth();

  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [newSaleOpen, setNewSaleOpen] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [voiding, setVoiding] = useState(null);
  const [busy, setBusy] = useState(false);

  const debouncedSearch = useDebounced(search);

  const filters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      payment_method: paymentMethod || undefined,
    }),
    [debouncedSearch, dateFrom, dateTo, paymentMethod],
  );
  const list = usePaginatedList(salesApi.list, filters, 15);

  const { data: detail, loading: detailLoading } = useApi(
    () => salesApi.get(detailId),
    [detailId],
    { skip: !detailId },
  );

  const confirmVoid = async () => {
    setBusy(true);
    try {
      await salesApi.void(voiding.id);
      toast.success('Sale voided and stock restored.');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setVoiding(null);
      setBusy(false);
    }
  };

  const columns = [
    {
      key: 'bill_no',
      header: 'Bill',
      render: (row) => <span className="font-mono text-xs">{row.bill_no}</span>,
    },
    {
      key: 'sale_date',
      header: 'Date',
      render: (row) => (
        <span className="whitespace-nowrap">{formatDate(row.sale_date, { withTime: true })}</span>
      ),
    },
    { key: 'customer_name', header: 'Customer', render: (row) => row.customer_name || 'Walk-in' },
    { key: 'employee_name', header: 'Sold by', render: (row) => row.employee_name || '—' },
    { key: 'item_count', header: 'Items', align: 'right' },
    {
      key: 'payment_method',
      header: 'Payment',
      render: (row) => (
        <Badge className="bg-slate-100 text-slate-600">{humanise(row.payment_method)}</Badge>
      ),
    },
    {
      key: 'total_amount',
      header: 'Total',
      align: 'right',
      render: (row) => <span className="font-medium">{formatCurrency(row.total_amount)}</span>,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button
            type="button"
            className="btn-ghost p-1.5"
            onClick={() => setDetailId(row.id)}
            title="View bill"
          >
            <Eye className="h-4 w-4" />
          </button>
          {isManager && (
            <button
              type="button"
              className="btn-ghost p-1.5 text-red-600 hover:bg-red-50"
              onClick={() => setVoiding(row)}
              title="Void sale"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Sales"
        description="Every bill raised, with full line item detail."
        actions={
          <button type="button" className="btn-primary" onClick={() => setNewSaleOpen(true)}>
            <Plus className="h-4 w-4" />
            New sale
          </button>
        }
      />

      <Card bodyClassName="p-0">
        <div className="grid grid-cols-1 gap-3 border-b border-surface-border p-4 sm:grid-cols-2 lg:grid-cols-4">
          <SearchInput value={search} onChange={setSearch} placeholder="Bill number…" />
          <div className="flex items-center gap-2">
            <input
              type="date"
              className="input"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
              aria-label="From date"
            />
            <span className="text-xs text-slate-400">to</span>
            <input
              type="date"
              className="input"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
              aria-label="To date"
            />
          </div>
          <Select
            value={paymentMethod}
            onChange={(event) => setPaymentMethod(event.target.value)}
            options={PAYMENT_METHODS.map((method) => ({
              value: method,
              label: humanise(method),
            }))}
            placeholder="All payment methods"
          />
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              setSearch('');
              setDateFrom('');
              setDateTo('');
              setPaymentMethod('');
            }}
          >
            Clear filters
          </button>
        </div>

        <DataTable
          columns={columns}
          rows={list.items}
          loading={list.loading}
          error={list.error}
          onRetry={list.reload}
          emptyTitle="No sales match your filters"
        />

        <Pagination
          page={list.page}
          totalPages={list.totalPages}
          total={list.total}
          pageSize={15}
          onChange={list.setPage}
        />
      </Card>

      <NewSale
        open={newSaleOpen}
        onClose={() => setNewSaleOpen(false)}
        onCreated={() => {
          setNewSaleOpen(false);
          list.reload();
        }}
      />

      <Modal
        open={Boolean(detailId)}
        title={detail ? `Bill ${detail.bill_no}` : 'Bill'}
        onClose={() => setDetailId(null)}
        width="max-w-2xl"
      >
        {detailLoading ? (
          <Loading />
        ) : detail ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Info label="Date" value={formatDate(detail.sale_date, { withTime: true })} />
              <Info label="Customer" value={detail.customer_name || 'Walk-in'} />
              <Info label="Sold by" value={detail.employee_name || '—'} />
              <Info label="Payment" value={humanise(detail.payment_method)} />
            </div>

            <div className="table-wrap rounded-lg border border-surface-border">
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="text-right">Qty</th>
                    <th className="text-right">Unit price</th>
                    <th className="text-right">Discount</th>
                    <th className="text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.product_name}</td>
                      <td className="text-right">{item.quantity}</td>
                      <td className="text-right">{formatCurrency(item.unit_price)}</td>
                      <td className="text-right">{formatCurrency(item.discount_amount)}</td>
                      <td className="text-right font-medium">{formatCurrency(item.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="ml-auto w-full max-w-xs space-y-1.5 text-sm">
              <Row label="Subtotal" value={formatCurrency(detail.subtotal)} />
              <Row label="Bill discount" value={`- ${formatCurrency(detail.discount_amount)}`} />
              <Row label="Taxable amount" value={formatCurrency(detail.taxable_amount)} />
              <Row label={`GST (${detail.gst_rate}%)`} value={formatCurrency(detail.gst_amount)} />
              <div className="flex justify-between border-t border-surface-border pt-2 text-base font-semibold text-slate-900">
                <span>Total</span>
                <span>{formatCurrency(detail.total_amount)}</span>
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={Boolean(voiding)}
        title="Void sale"
        message={`Void bill ${voiding?.bill_no}? The sale will be removed and all stock returned to inventory.`}
        confirmLabel="Void sale"
        busy={busy}
        onConfirm={confirmVoid}
        onClose={() => setVoiding(null)}
      />
    </>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 font-medium text-slate-900">{value}</p>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between text-slate-600">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
