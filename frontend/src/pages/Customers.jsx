import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { customerApi } from '../api/endpoints';
import { DataTable, Pagination, SearchInput } from '../components/ui/DataTable';
import {
  Card,
  ConfirmDialog,
  Field,
  Loading,
  Modal,
  PageHeader,
  Select,
  Spinner,
} from '../components/ui';
import { useToast } from '../components/ui/Toast';
import { useApi, useDebounced, usePaginatedList } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { formatCurrency, formatDate, formatNumber } from '../utils/format';

const EMPTY_FORM = { name: '', phone: '', email: '', city: '', address: '' };

export default function Customers() {
  const toast = useToast();
  const { isManager } = useAuth();

  const [search, setSearch] = useState('');
  const [city, setCity] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [detailId, setDetailId] = useState(null);

  const debouncedSearch = useDebounced(search);
  const { data: cities } = useApi(() => customerApi.cities(), []);

  const filters = useMemo(
    () => ({ search: debouncedSearch || undefined, city: city || undefined }),
    [debouncedSearch, city],
  );
  const list = usePaginatedList(customerApi.list, filters, 15);

  const { data: detail, loading: detailLoading } = useApi(
    () => customerApi.get(detailId),
    [detailId],
    { skip: !detailId },
  );

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError('');
    setFormOpen(true);
  };

  const openEdit = (customer) => {
    setEditing(customer);
    setForm({
      name: customer.name,
      phone: customer.phone ?? '',
      email: customer.email ?? '',
      city: customer.city ?? '',
      address: customer.address ?? '',
    });
    setFormError('');
    setFormOpen(true);
  };

  const submitForm = async (event) => {
    event.preventDefault();
    setSaving(true);
    setFormError('');
    const payload = {
      name: form.name.trim(),
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      city: form.city.trim() || null,
      address: form.address.trim() || null,
    };
    try {
      if (editing) {
        await customerApi.update(editing.id, payload);
        toast.success('Customer updated.');
      } else {
        await customerApi.create(payload);
        toast.success('Customer created.');
      }
      setFormOpen(false);
      list.reload();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      await customerApi.remove(deleting.id);
      toast.success('Customer deleted.');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setDeleting(null);
      setBusy(false);
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'Customer',
      render: (row) => (
        <div>
          <p className="font-medium text-slate-900">{row.name}</p>
          <p className="font-mono text-xs text-slate-500">{row.customer_code}</p>
        </div>
      ),
    },
    { key: 'phone', header: 'Phone', render: (row) => row.phone || '—' },
    { key: 'email', header: 'Email', render: (row) => row.email || '—' },
    { key: 'city', header: 'City', render: (row) => row.city || '—' },
    {
      key: 'created_at',
      header: 'Added',
      render: (row) => formatDate(row.created_at),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button
            type="button"
            className="btn-ghost px-2 py-1 text-xs"
            onClick={(event) => {
              event.stopPropagation();
              setDetailId(row.id);
            }}
          >
            History
          </button>
          <button
            type="button"
            className="btn-ghost p-1.5"
            onClick={(event) => {
              event.stopPropagation();
              openEdit(row);
            }}
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </button>
          {isManager && (
            <button
              type="button"
              className="btn-ghost p-1.5 text-red-600 hover:bg-red-50"
              onClick={(event) => {
                event.stopPropagation();
                setDeleting(row);
              }}
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      ),
    },
  ];

  const summary = detail?.purchase_summary;

  return (
    <>
      <PageHeader
        title="Customers"
        description="Customer records and their buying behaviour."
        actions={
          <button type="button" className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" />
            New customer
          </button>
        }
      />

      <Card bodyClassName="p-0">
        <div className="flex flex-col gap-3 border-b border-surface-border p-4 sm:flex-row">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name, code, phone or email…"
            className="sm:max-w-sm"
          />
          <Select
            value={city}
            onChange={(event) => setCity(event.target.value)}
            options={cities ?? []}
            placeholder="All cities"
          />
        </div>

        <DataTable
          columns={columns}
          rows={list.items}
          loading={list.loading}
          error={list.error}
          onRetry={list.reload}
          emptyTitle="No customers found"
        />

        <Pagination
          page={list.page}
          totalPages={list.totalPages}
          total={list.total}
          pageSize={15}
          onChange={list.setPage}
        />
      </Card>

      <Modal
        open={formOpen}
        title={editing ? `Edit ${editing.name}` : 'New customer'}
        onClose={() => setFormOpen(false)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setFormOpen(false)}>
              Cancel
            </button>
            <button type="submit" form="customer-form" className="btn-primary" disabled={saving}>
              {saving && <Spinner className="h-4 w-4 text-white" />}
              {editing ? 'Save changes' : 'Create customer'}
            </button>
          </>
        }
      >
        <form id="customer-form" onSubmit={submitForm} className="space-y-4">
          {formError && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {formError}
            </p>
          )}
          <Field label="Name" required>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              minLength={2}
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Phone">
              <input
                className="input"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="9876543210"
              />
            </Field>
            <Field label="Email">
              <input
                type="email"
                className="input"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
          </div>
          <Field label="City">
            <input
              className="input"
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
            />
          </Field>
          <Field label="Address">
            <input
              className="input"
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        open={Boolean(detailId)}
        title={detail ? `${detail.name} — purchase history` : 'Customer'}
        onClose={() => setDetailId(null)}
        width="max-w-lg"
      >
        {detailLoading ? (
          <Loading />
        ) : summary ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Total orders" value={formatNumber(summary.total_orders)} />
              <Stat label="Total spent" value={formatCurrency(summary.total_spent)} />
              <Stat label="Average order" value={formatCurrency(summary.average_order_value)} />
              <Stat
                label="Last purchase"
                value={
                  summary.days_since_last_purchase !== null
                    ? `${summary.days_since_last_purchase} days ago`
                    : '—'
                }
              />
            </div>
            {summary.favourite_category && (
              <p className="text-sm text-slate-600">
                Most spend is in <strong>{summary.favourite_category}</strong>.
              </p>
            )}
            {detail.recent_bills?.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Recent bills
                </p>
                <ul className="space-y-1">
                  {detail.recent_bills.map((bill) => (
                    <li key={bill} className="font-mono text-xs text-slate-600">
                      {bill}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            This customer has not made any purchases yet.
          </p>
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete customer"
        message={`Delete "${deleting?.name}"? Customers with purchase history cannot be deleted.`}
        confirmLabel="Delete"
        busy={busy}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}
