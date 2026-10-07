import { RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { aiApi, authApi, forecastApi } from '../api/endpoints';
import { Badge, Card, Field, Loading, PageHeader, Spinner } from '../components/ui';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { formatDate, humanise } from '../utils/format';

export default function Settings() {
  const toast = useToast();
  const { user, isManager, isOwner } = useAuth();

  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' });
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const aiStatus = useApi(() => aiApi.status(), []);
  const modelStatus = useApi(() => forecastApi.status(), []);
  const users = useApi(() => authApi.listUsers(), [], { skip: !isManager });

  const changePassword = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await authApi.changePassword(passwords);
      toast.success('Password updated.');
      setPasswords({ current_password: '', new_password: '' });
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const refreshModels = async () => {
    setRefreshing(true);
    try {
      await forecastApi.refreshCache();
      toast.success('Model cache cleared.');
      modelStatus.reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <>
      <PageHeader title="Settings" description="Your account, models and system configuration." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Your account">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Item label="Name" value={user?.full_name} />
            <Item label="Email" value={user?.email} />
            <Item label="Role" value={humanise(user?.role)} />
            <Item label="Last sign in" value={formatDate(user?.last_login_at, { withTime: true })} />
          </dl>
        </Card>

        <Card title="Change password">
          <form onSubmit={changePassword} className="space-y-3">
            <Field label="Current password" required>
              <input
                type="password"
                className="input"
                value={passwords.current_password}
                onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })}
                autoComplete="current-password"
                required
              />
            </Field>
            <Field label="New password" required hint="At least 8 characters, with a letter and a digit">
              <input
                type="password"
                className="input"
                value={passwords.new_password}
                onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })}
                autoComplete="new-password"
                minLength={8}
                required
              />
            </Field>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving && <Spinner className="h-4 w-4 text-white" />}
              Update password
            </button>
          </form>
        </Card>

        <Card
          title="Machine learning models"
          action={
            isManager && (
              <button
                type="button"
                className="btn-secondary text-xs"
                onClick={refreshModels}
                disabled={refreshing}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                Reload
              </button>
            )
          }
        >
          {modelStatus.loading ? (
            <Loading className="py-6" />
          ) : modelStatus.data ? (
            <div className="space-y-3">
              <ModelRow
                label="Sales forecasting"
                trained={modelStatus.data.sales_model_trained}
                model={modelStatus.data.sales_model}
              />
              <ModelRow
                label="Demand forecasting"
                trained={modelStatus.data.demand_model_trained}
                model={modelStatus.data.demand_model}
              />
              <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                Models are trained offline. To retrain from the latest sales history run{' '}
                <code className="rounded bg-slate-200 px-1 py-0.5 font-mono">
                  python -m app.scripts.train_models
                </code>{' '}
                in the backend directory.
              </p>
            </div>
          ) : null}
        </Card>

        <Card title="AI assistant">
          {aiStatus.loading ? (
            <Loading className="py-6" />
          ) : aiStatus.data ? (
            <div className="space-y-3 text-sm">
              <dl className="grid grid-cols-2 gap-3">
                <Item label="Configured provider" value={aiStatus.data.provider.configured} />
                <Item label="Active provider" value={aiStatus.data.provider.active} />
                <Item label="Model" value={aiStatus.data.provider.model ?? '—'} />
                <Item
                  label="Agents"
                  value={String(aiStatus.data.agents.length)}
                />
              </dl>
              <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                {aiStatus.data.grounding}
              </p>
              {aiStatus.data.provider.offline_fallback && (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  Running in offline mode. Answers are still built from your real data. To use a
                  language model, set LLM_PROVIDER and LLM_API_KEY in the backend .env file.
                </p>
              )}
            </div>
          ) : null}
        </Card>

        {isManager && (
          <Card title="Platform users" className="lg:col-span-2" bodyClassName="p-0">
            {users.loading ? (
              <Loading className="py-6" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Last sign in</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(users.data ?? []).map((row) => (
                      <tr key={row.id}>
                        <td className="font-medium text-slate-900">{row.full_name}</td>
                        <td>{row.email}</td>
                        <td>
                          <Badge className="bg-slate-100 text-slate-600">
                            {humanise(row.role)}
                          </Badge>
                        </td>
                        <td>
                          <Badge
                            className={
                              row.is_active
                                ? 'bg-emerald-50 text-emerald-700'
                                : 'bg-slate-100 text-slate-500'
                            }
                          >
                            {row.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </td>
                        <td className="text-xs text-slate-500">
                          {formatDate(row.last_login_at, { withTime: true })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {isOwner && (
              <p className="border-t border-surface-border px-5 py-3 text-xs text-slate-500">
                As the owner you can create and deactivate accounts through the API. User
                management screens can be added here as the team grows.
              </p>
            )}
          </Card>
        )}
      </div>
    </>
  );
}

function Item({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 truncate font-medium text-slate-900">{value ?? '—'}</dd>
    </div>
  );
}

function ModelRow({ label, trained, model }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-surface-border px-3 py-2">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-900">{label}</p>
        {model && (
          <p className="truncate text-xs text-slate-500">
            {model.algorithm} · trained {formatDate(model.trained_at)}
          </p>
        )}
      </div>
      <Badge
        className={
          trained
            ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
            : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
        }
      >
        {trained ? 'Trained' : 'Not trained'}
      </Badge>
    </div>
  );
}
