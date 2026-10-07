import { Search, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { customerApi, employeeApi, productApi, salesApi } from '../../api/endpoints';
import { Field, Modal, Select, Spinner } from '../../components/ui';
import { useToast } from '../../components/ui/Toast';
import { useApi, useDebounced } from '../../hooks/useApi';
import { PAYMENT_METHODS } from '../../utils/constants';
import { formatCurrency, humanise } from '../../utils/format';

const GST_RATE = 18;

/**
 * Sale builder. Totals are computed live using the same rules as the backend
 * so the operator sees the final bill before committing, and the backend
 * remains the authority that actually validates stock and writes the sale.
 */
export default function NewSale({ open, onClose, onCreated }) {
  const toast = useToast();

  const [lines, setLines] = useState([]);
  const [customerId, setCustomerId] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [billDiscount, setBillDiscount] = useState('0');
  const [notes, setNotes] = useState('');
  const [productQuery, setProductQuery] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const debouncedQuery = useDebounced(productQuery, 300);

  const { data: customers } = useApi(
    () => customerApi.list({ page_size: 200, sort_by: 'name' }),
    [],
    { skip: !open },
  );
  const { data: employees } = useApi(
    () => employeeApi.list({ page_size: 100, sort_by: 'name' }),
    [],
    { skip: !open },
  );
  const { data: matches } = useApi(
    () => (debouncedQuery.length >= 2 ? productApi.search(debouncedQuery, 8) : Promise.resolve([])),
    [debouncedQuery],
    { skip: !open },
  );

  useEffect(() => {
    if (!open) {
      setLines([]);
      setCustomerId('');
      setEmployeeId('');
      setPaymentMethod('cash');
      setBillDiscount('0');
      setNotes('');
      setProductQuery('');
      setError('');
    }
  }, [open]);

  const addProduct = (product) => {
    setProductQuery('');
    setLines((current) => {
      if (current.some((line) => line.product_id === product.id)) {
        toast.info(`${product.name} is already on this bill.`);
        return current;
      }
      return [
        ...current,
        {
          product_id: product.id,
          name: product.name,
          sku: product.sku,
          available: product.stock,
          unit_price: Number(product.selling_price),
          quantity: 1,
          discount_amount: 0,
        },
      ];
    });
  };

  const updateLine = (productId, patch) => {
    setLines((current) =>
      current.map((line) => (line.product_id === productId ? { ...line, ...patch } : line)),
    );
  };

  const removeLine = (productId) => {
    setLines((current) => current.filter((line) => line.product_id !== productId));
  };

  const totals = useMemo(() => {
    const subtotal = lines.reduce(
      (sum, line) =>
        sum + Math.max(line.unit_price * line.quantity - (Number(line.discount_amount) || 0), 0),
      0,
    );
    const discount = Math.min(Number(billDiscount) || 0, subtotal);
    const taxable = subtotal - discount;
    const gst = (taxable * GST_RATE) / 100;
    return { subtotal, discount, taxable, gst, total: taxable + gst };
  }, [lines, billDiscount]);

  const overStock = lines.filter((line) => line.quantity > line.available);
  const canSubmit = lines.length > 0 && overStock.length === 0 && !submitting;

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const result = await salesApi.create({
        customer_id: customerId ? Number(customerId) : null,
        employee_id: employeeId ? Number(employeeId) : null,
        payment_method: paymentMethod,
        discount_amount: String(Number(billDiscount) || 0),
        notes: notes.trim() || null,
        items: lines.map((line) => ({
          product_id: line.product_id,
          quantity: Number(line.quantity),
          discount_amount: String(Number(line.discount_amount) || 0),
        })),
      });
      toast.success(
        `Bill ${result.sale.bill_no} created for ${formatCurrency(result.sale.total_amount)}.`,
      );
      result.alerts_raised?.forEach((message) => toast.info(message));
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="New sale"
      onClose={onClose}
      width="max-w-4xl"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="sale-form" className="btn-primary" disabled={!canSubmit}>
            {submitting && <Spinner className="h-4 w-4 text-white" />}
            Complete sale · {formatCurrency(totals.total)}
          </button>
        </>
      }
    >
      <form id="sale-form" onSubmit={submit} className="space-y-5">
        {error && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {/* Product search */}
        <div className="relative">
          <Field label="Add products" hint="Search by product name or SKU">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className="input pl-9"
                value={productQuery}
                onChange={(event) => setProductQuery(event.target.value)}
                placeholder="Start typing a product name…"
              />
            </div>
          </Field>

          {matches?.length > 0 && productQuery.length >= 2 && (
            <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-surface-border bg-white shadow-raised">
              {matches.map((product) => (
                <li key={product.id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 disabled:opacity-50"
                    onClick={() => addProduct(product)}
                    disabled={product.stock <= 0}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-slate-900">
                        {product.name}
                      </span>
                      <span className="font-mono text-xs text-slate-500">{product.sku}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block text-sm font-medium">
                        {formatCurrency(product.selling_price)}
                      </span>
                      <span
                        className={`block text-xs ${
                          product.stock <= 0 ? 'text-red-600' : 'text-slate-500'
                        }`}
                      >
                        {product.stock <= 0 ? 'Out of stock' : `${product.stock} in stock`}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Line items */}
        {lines.length > 0 ? (
          <div className="table-wrap rounded-lg border border-surface-border">
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="text-right">Qty</th>
                  <th className="text-right">Unit price</th>
                  <th className="text-right">Discount</th>
                  <th className="text-right">Total</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => {
                  const lineTotal = Math.max(
                    line.unit_price * line.quantity - (Number(line.discount_amount) || 0),
                    0,
                  );
                  const exceeds = line.quantity > line.available;
                  return (
                    <tr key={line.product_id}>
                      <td>
                        <p className="font-medium text-slate-900">{line.name}</p>
                        <p className={`text-xs ${exceeds ? 'text-red-600' : 'text-slate-500'}`}>
                          {exceeds
                            ? `Only ${line.available} available`
                            : `${line.available} in stock`}
                        </p>
                      </td>
                      <td className="text-right">
                        <input
                          type="number"
                          min="1"
                          max={line.available}
                          className={`input w-20 text-right ${exceeds ? 'border-red-400' : ''}`}
                          value={line.quantity}
                          onChange={(event) =>
                            updateLine(line.product_id, {
                              quantity: Math.max(1, Number(event.target.value) || 1),
                            })
                          }
                        />
                      </td>
                      <td className="text-right">{formatCurrency(line.unit_price)}</td>
                      <td className="text-right">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          className="input w-24 text-right"
                          value={line.discount_amount}
                          onChange={(event) =>
                            updateLine(line.product_id, {
                              discount_amount: Number(event.target.value) || 0,
                            })
                          }
                        />
                      </td>
                      <td className="text-right font-medium">{formatCurrency(lineTotal)}</td>
                      <td className="text-right">
                        <button
                          type="button"
                          className="btn-ghost p-1.5 text-red-600 hover:bg-red-50"
                          onClick={() => removeLine(line.product_id)}
                          aria-label={`Remove ${line.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-surface-border py-8 text-center text-sm text-slate-500">
            Search above to add products to this bill.
          </p>
        )}

        {/* Bill details and totals */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="space-y-4">
            <Field label="Customer">
              <Select
                value={customerId}
                onChange={(event) => setCustomerId(event.target.value)}
                placeholder="Walk-in customer"
                options={(customers?.items ?? []).map((customer) => ({
                  value: customer.id,
                  label: `${customer.name} (${customer.customer_code})`,
                }))}
              />
            </Field>
            <Field label="Sold by">
              <Select
                value={employeeId}
                onChange={(event) => setEmployeeId(event.target.value)}
                placeholder="Not specified"
                options={(employees?.items ?? []).map((employee) => ({
                  value: employee.id,
                  label: `${employee.name} — ${employee.role}`,
                }))}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Payment method">
                <Select
                  value={paymentMethod}
                  onChange={(event) => setPaymentMethod(event.target.value)}
                  options={PAYMENT_METHODS.map((method) => ({
                    value: method,
                    label: humanise(method),
                  }))}
                />
              </Field>
              <Field label="Bill discount">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="input"
                  value={billDiscount}
                  onChange={(event) => setBillDiscount(event.target.value)}
                />
              </Field>
            </div>
            <Field label="Notes">
              <input
                className="input"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Optional"
              />
            </Field>
          </div>

          <div className="rounded-lg bg-slate-50 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Bill summary
            </p>
            <dl className="space-y-2 text-sm">
              <SummaryRow label="Subtotal" value={formatCurrency(totals.subtotal)} />
              <SummaryRow label="Bill discount" value={`- ${formatCurrency(totals.discount)}`} />
              <SummaryRow label="Taxable amount" value={formatCurrency(totals.taxable)} />
              <SummaryRow label={`GST (${GST_RATE}%)`} value={formatCurrency(totals.gst)} />
              <div className="flex justify-between border-t border-slate-300 pt-2 text-base font-semibold text-slate-900">
                <dt>Total payable</dt>
                <dd>{formatCurrency(totals.total)}</dd>
              </div>
            </dl>
            {overStock.length > 0 && (
              <p className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                <X className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Reduce quantities: not enough stock for {overStock.length} item(s).
              </p>
            )}
          </div>
        </div>
      </form>
    </Modal>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex justify-between text-slate-600">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
