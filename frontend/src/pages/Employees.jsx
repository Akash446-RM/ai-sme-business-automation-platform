import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { employeeApi } from '../api/endpoints';
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

const EMPTY_FORM = { name: '', role: '', department: '', phone: '', email: '', hired_on: '' };

export default function Employees() {
  const toast = useToast();
  const { isManager } = useAuth();

  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [performanceId, setPerformanceId] = useState(null);

  const debouncedSearch = useDebounced(search);
  const { data: roles } = useApi(() => employeeApi.roles(), []);

  const filters = useMemo(
    () => ({ search: debouncedSearch || undefined, role: role || undefined }),
    [debouncedSearch, role],
  );
  const list = usePaginatedList(employeeApi.list, filters, 15);

  const { data: performance, loading: performanceLoading } = useApi(
    () => employeeApi.performance(performanceId),
    [performanceId],
    { skip: !performanceId },
  );

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError('');
    setFormOpen(true);
  };

  const openEdit = (employee) => {
    setEditing(employee);
    setForm({
      name: employee.name,
      role: employee.role,
      department: employee.department ?? '',
      phone: employee.phone ?? '',
      email: employee.email ?? '',
      hired_on: employee.hired_on ?? '',
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
      role: form.role.trim(),
      department: form.department.trim() || null,
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      hired_on: form.hired_on || null,
    };
    try {
      if (editing) {
        await employeeApi.update(editing.id, payload);
        toast.success('Employee updated.');
      } else {
        await employeeApi.create(payload);
        toast.success('Employee created.');
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
      await employeeApi.remove(deleting.id);
      toast.success('Employee deleted.');
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
      header: 'Employee',
      render: (row) => (
        <div>
          <p className="font-medium text-slate-900">{row.name}</p>
          <p className="font-mono text-xs text-slate-500">{row.employee_code}</p>
        </div>
      ),
    },
    { key: 'role', header: 'Role' },
    { key: 'department', header: 'Department', render: (row) => row.department || '—' },
    { key: 'phone', header: 'Phone', render: (row) => row.phone || '—' },
    { key: 'hired_on', header: 'Hired', render: (row) => formatDate(row.hired_on) },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <div className="flex justify-end gap-1">
          <button
            type="button"
            className="btn-ghost px-2 py-1 text-xs"
            onClick={() => setPerformanceId(row.id)}
          >
            Performance
          </button>
          {isManager && (
            <>
              <button type="button" className="btn-ghost p-1.5" onClick={() => openEdit(row)} title="Edit">
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
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Employees"
        description="Your team and the sales attributed to each person."
        actions={
          isManager && (
            <button type="button" className="btn-primary" onClick={openCreate}>
              <Plus className="h-4 w-4" />
              New employee
            </button>
          )
        }
      />

      <Card bodyClassName="p-0">
        <div className="flex flex-col gap-3 border-b border-surface-border p-4 sm:flex-row">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by name, code or email…"
            className="sm:max-w-sm"
          />
          <Select
            value={role}
            onChange={(event) => setRole(event.target.value)}
            options={roles ?? []}
            placeholder="All roles"
          />
        </div>

        <DataTable
          columns={columns}
          rows={list.items}
          loading={list.loading}
          error={list.error}
          onRetry={list.reload}
          emptyTitle="No employees found"
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
        title={editing ? `Edit ${editing.name}` : 'New employee'}
        onClose={() => setFormOpen(false)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setFormOpen(false)}>
              Cancel
            </button>
            <button type="submit" form="employee-form" className="btn-primary" disabled={saving}>
              {saving && <Spinner className="h-4 w-4 text-white" />}
              {editing ? 'Save changes' : 'Create employee'}
            </button>
          </>
        }
      >
        <form id="employee-form" onSubmit={submitForm} className="space-y-4">
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
            <Field label="Role" required>
              <input
                className="input"
                list="role-options"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                required
              />
              <datalist id="role-options">
                {(roles ?? []).map((item) => (
                  <option key={item} value={item} />
                ))}
              </datalist>
            </Field>
            <Field label="Department">
              <input
                className="input"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </Field>
            <Field label="Phone">
              <input
                className="input"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
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
          <Field label="Hired on">
            <input
              type="date"
              className="input"
              value={form.hired_on}
              onChange={(e) => setForm({ ...form, hired_on: e.target.value })}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        open={Boolean(performanceId)}
        title={performance ? `${performance.name} — performance` : 'Performance'}
        onClose={() => setPerformanceId(null)}
        width="max-w-md"
      >
        {performanceLoading ? (
          <Loading />
        ) : performance ? (
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Total sales" value={formatNumber(performance.total_sales)} />
            <Stat label="Revenue" value={formatCurrency(performance.total_revenue)} />
            <Stat label="Average order" value={formatCurrency(performance.average_order_value)} />
            <Stat label="Last sale" value={formatDate(performance.last_sale_at)} />
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete employee"
        message={`Delete "${deleting?.name}"? Employees linked to sales cannot be deleted.`}
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
