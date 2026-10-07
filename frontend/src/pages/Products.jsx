import { Pencil, PackagePlus, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { productApi } from '../api/endpoints';
import { DataTable, Pagination, SearchInput } from '../components/ui/DataTable';
import {
  Badge,
  Card,
  ConfirmDialog,
  Field,
  Modal,
  PageHeader,
  Select,
  Spinner,
} from '../components/ui';
import { useToast } from '../components/ui/Toast';
import { useApi, useDebounced, usePaginatedList } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { STOCK_STATUS_STYLES } from '../utils/constants';
import { formatCurrency, formatNumber, humanise } from '../utils/format';

const EMPTY_FORM = {
  name: '',
  sku: '',
  category: '',
  barcode: '',
  supplier: '',
  cost_price: '',
  selling_price: '',
  stock: '0',
  reorder_level: '10',
  max_stock_level: '',
  lead_time_days: '5',
  description: '',
};

export default function Products() {
  const toast = useToast();
  const { isManager } = useAuth();

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [stockFilter, setStockFilter] = useState('');
  const [sortBy, setSortBy] = useState('name');
  const [sortDir, setSortDir] = useState('asc');

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const [adjusting, setAdjusting] = useState(null);
  const [adjustment, setAdjustment] = useState({ quantity: '', reason: '' });
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);

  const debouncedSearch = useDebounced(search);
  const { data: categories } = useApi(() => productApi.categories(), []);

  const filters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      category: category || undefined,
      low_stock_only: stockFilter === 'low' || undefined,
      out_of_stock_only: stockFilter === 'out' || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
    [debouncedSearch, category, stockFilter, sortBy, sortDir],
  );

  const list = usePaginatedList(productApi.list, filters, 15);

  const onSort = (key) => {
    if (sortBy === key) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('asc');
    }
  };

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError('');
    setFormOpen(true);
  };

  const openEdit = (product) => {
    setEditing(product);
    setForm({
      name: product.name,
      sku: product.sku,
      category: product.category,
      barcode: product.barcode ?? '',
      supplier: product.supplier ?? '',
      cost_price: String(product.cost_price),
      selling_price: String(product.selling_price),
      stock: String(product.stock),
      reorder_level: String(product.reorder_level),
      max_stock_level: product.max_stock_level ? String(product.max_stock_level) : '',
      lead_time_days: String(product.lead_time_days),
      description: product.description ?? '',
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
      category: form.category.trim(),
      cost_price: form.cost_price,
      selling_price: form.selling_price,
      reorder_level: Number(form.reorder_level),
      lead_time_days: Number(form.lead_time_days),
      barcode: form.barcode.trim() || null,
      supplier: form.supplier.trim() || null,
      description: form.description.trim() || null,
      max_stock_level: form.max_stock_level ? Number(form.max_stock_level) : null,
    };

    try {
      if (editing) {
        await productApi.update(editing.id, payload);
        toast.success(`${payload.name} updated.`);
      } else {
        await productApi.create({
          ...payload,
          sku: form.sku.trim(),
          stock: Number(form.stock),
        });
        toast.success(`${payload.name} created.`);
      }
      setFormOpen(false);
      list.reload();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const submitAdjustment = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await productApi.adjustStock(adjusting.id, {
        quantity: Number(adjustment.quantity),
        reason: adjustment.reason.trim(),
      });
      toast.success('Stock adjusted and recorded in the ledger.');
      setAdjusting(null);
      setAdjustment({ quantity: '', reason: '' });
      list.reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      await productApi.remove(deleting.id);
      toast.success('Product deleted.');
      setDeleting(null);
      list.reload();
    } catch (err) {
      toast.error(err.message);
      setDeleting(null);
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'Product',
      sortable: true,
      render: (row) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-slate-900">{row.name}</p>
          <p className="font-mono text-xs text-slate-500">{row.sku}</p>
        </div>
      ),
    },
    { key: 'category', header: 'Category', sortable: true },
    {
      key: 'selling_price',
      header: 'Price',
      sortable: true,
      align: 'right',
      render: (row) => (
        <div>
          <p className="font-medium">{formatCurrency(row.selling_price)}</p>
          <p className="text-xs text-slate-500">cost {formatCurrency(row.cost_price)}</p>
        </div>
      ),
    },
    {
      key: 'margin',
      header: 'Margin',
      align: 'right',
      render: (row) => `${row.margin_percent?.toFixed(1) ?? '0.0'}%`,
    },
    {
      key: 'stock',
      header: 'Stock',
      sortable: true,
      align: 'right',
      render: (row) => (
        <div>
          <p className="font-medium">{formatNumber(row.stock)}</p>
          <p className="text-xs text-slate-500">reorder at {row.reorder_level}</p>
        </div>
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
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) =>
        isManager && (
          <div className="flex justify-end gap-1">
            <button
              type="button"
              className="btn-ghost p-1.5"
              onClick={() => setAdjusting(row)}
              title="Adjust stock"
            >
              <PackagePlus className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="btn-ghost p-1.5"
              onClick={() => openEdit(row)}
              title="Edit"
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="btn-ghost p-1.5 text-red-600 hover:bg-red-50"
              onClick={() => setDeleting(row)}
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Products"
        description="Your catalogue, pricing and stock position."
        actions={
          isManager && (
            <button type="button" className="btn-primary" onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New product
            </button>
          )
        }
      />

      <Card bodyClassName="p-0">
        <div className="flex flex-col gap-3 border-b border-surface-border p-4 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name, SKU or barcode…"
            className="sm:max-w-xs"
          />
          <div className="flex flex-1 gap-2">
            <Select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              options={categories ?? []}
              placeholder="All categories"
            />
            <Select
              value={stockFilter}
              onChange={(event) => setStockFilter(event.target.value)}
              options={[
                { value: 'low', label: 'Low stock' },
                { value: 'out', label: 'Out of stock' },
              ]}
              placeholder="All stock levels"
            />
          </div>
        </div>

        <DataTable
          columns={columns}
          rows={list.items}
          loading={list.loading}
          error={list.error}
          onRetry={list.reload}
          sortBy={sortBy}
          sortDir={sortDir}
          onSort={onSort}
          emptyTitle="No products match your filters"
          emptyMessage="Try clearing the search or filters."
        />

        <Pagination
          page={list.page}
          totalPages={list.totalPages}
          total={list.total}
          pageSize={15}
          onChange={list.setPage}
        />
      </Card>

      {/* Create / edit */}
      <Modal
        open={formOpen}
        title={editing ? `Edit ${editing.name}` : 'New product'}
        onClose={() => setFormOpen(false)}
        width="max-w-2xl"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setFormOpen(false)}>
              Cancel
            </button>
            <button type="submit" form="product-form" className="btn-primary" disabled={saving}>
              {saving && <Spinner className="h-4 w-4 text-white" />}
              {editing ? 'Save changes' : 'Create product'}
            </button>
          </>
        }
      >
        <form id="product-form" onSubmit={submitForm} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {formError && (
            <p className="sm:col-span-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {formError}
            </p>
          )}

          <div className="sm:col-span-2">
            <Field label="Product name" required>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                minLength={2}
              />
            </Field>
          </div>

          <Field label="SKU" required hint={editing ? 'SKU cannot be changed' : undefined}>
            <input
              className="input"
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
              disabled={Boolean(editing)}
              required
            />
          </Field>

          <Field label="Category" required>
            <input
              className="input"
              list="category-options"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              required
            />
            <datalist id="category-options">
              {(categories ?? []).map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </Field>

          <Field label="Cost price" required>
            <input
              type="number"
              step="0.01"
              min="0"
              className="input"
              value={form.cost_price}
              onChange={(e) => setForm({ ...form, cost_price: e.target.value })}
              required
            />
          </Field>

          <Field label="Selling price" required hint="Must be at least the cost price">
            <input
              type="number"
              step="0.01"
              min="0"
              className="input"
              value={form.selling_price}
              onChange={(e) => setForm({ ...form, selling_price: e.target.value })}
              required
            />
          </Field>

          {!editing && (
            <Field label="Opening stock">
              <input
                type="number"
                min="0"
                className="input"
                value={form.stock}
                onChange={(e) => setForm({ ...form, stock: e.target.value })}
              />
            </Field>
          )}

          <Field label="Reorder level" hint="Alert when stock falls to this level">
            <input
              type="number"
              min="0"
              className="input"
              value={form.reorder_level}
              onChange={(e) => setForm({ ...form, reorder_level: e.target.value })}
            />
          </Field>

          <Field label="Maximum stock level">
            <input
              type="number"
              min="0"
              className="input"
              value={form.max_stock_level}
              onChange={(e) => setForm({ ...form, max_stock_level: e.target.value })}
            />
          </Field>

          <Field label="Supplier lead time (days)">
            <input
              type="number"
              min="0"
              className="input"
              value={form.lead_time_days}
              onChange={(e) => setForm({ ...form, lead_time_days: e.target.value })}
            />
          </Field>

          <Field label="Supplier">
            <input
              className="input"
              value={form.supplier}
              onChange={(e) => setForm({ ...form, supplier: e.target.value })}
            />
          </Field>

          <Field label="Barcode">
            <input
              className="input"
              value={form.barcode}
              onChange={(e) => setForm({ ...form, barcode: e.target.value })}
            />
          </Field>
        </form>
      </Modal>

      {/* Stock adjustment */}
      <Modal
        open={Boolean(adjusting)}
        title={`Adjust stock — ${adjusting?.name ?? ''}`}
        onClose={() => setAdjusting(null)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setAdjusting(null)}>
              Cancel
            </button>
            <button type="submit" form="adjust-form" className="btn-primary" disabled={busy}>
              {busy && <Spinner className="h-4 w-4 text-white" />}
              Apply adjustment
            </button>
          </>
        }
      >
        <form id="adjust-form" onSubmit={submitAdjustment} className="space-y-4">
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
            Current stock: <strong>{adjusting?.stock}</strong> units
          </p>
          <Field
            label="Quantity change"
            required
            hint="Use a positive number for received stock, negative for a write-off"
          >
            <input
              type="number"
              className="input"
              value={adjustment.quantity}
              onChange={(e) => setAdjustment({ ...adjustment, quantity: e.target.value })}
              required
            />
          </Field>
          <Field label="Reason" required>
            <input
              className="input"
              value={adjustment.reason}
              onChange={(e) => setAdjustment({ ...adjustment, reason: e.target.value })}
              placeholder="Supplier delivery received"
              minLength={3}
              required
            />
          </Field>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete product"
        message={`Delete "${deleting?.name}"? Products that appear in past sales cannot be deleted; deactivate them instead.`}
        confirmLabel="Delete"
        busy={busy}
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      />
    </>
  );
}
