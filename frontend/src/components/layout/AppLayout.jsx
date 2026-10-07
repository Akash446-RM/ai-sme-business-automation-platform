import {
  Bell,
  Boxes,
  ChartColumn,
  ChevronDown,
  FileBarChart,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Receipt,
  Settings,
  Sparkles,
  TrendingUp,
  UserRound,
  Users,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { alertApi } from '../../api/endpoints';
import { useAuth } from '../../context/AuthContext';

const NAVIGATION = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/employees', label: 'Employees', icon: UserRound },
  { to: '/sales', label: 'Sales', icon: Receipt },
  { to: '/inventory', label: 'Inventory', icon: Boxes },
  { to: '/analytics', label: 'Analytics', icon: ChartColumn },
  { to: '/forecasting', label: 'Forecasting', icon: TrendingUp },
  { to: '/assistant', label: 'AI Assistant', icon: Sparkles },
  { to: '/reports', label: 'Reports', icon: FileBarChart },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [openAlerts, setOpenAlerts] = useState(0);

  useEffect(() => setSidebarOpen(false), [location.pathname]);

  useEffect(() => {
    let active = true;
    alertApi
      .summary()
      .then((data) => active && setOpenAlerts(data.total_open))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [location.pathname]);

  return (
    <div className="min-h-screen">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 transform border-r border-surface-border bg-white transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center gap-2 border-b border-surface-border px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            S
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">SME Platform</p>
            <p className="truncate text-[11px] text-slate-500">Business Automation</p>
          </div>
          <button
            type="button"
            className="ml-auto lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        <nav className="flex flex-col gap-0.5 overflow-y-auto p-3" aria-label="Main">
          {NAVIGATION.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? 'bg-brand-50 font-medium text-brand-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden
        />
      )}

      {/* Main column */}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-surface-border bg-white/90 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            className="btn-ghost p-2 lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="ml-auto flex items-center gap-2">
            <NavLink
              to="/alerts"
              className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100"
              aria-label={`Alerts${openAlerts ? `, ${openAlerts} open` : ''}`}
            >
              <Bell className="h-5 w-5" />
              {openAlerts > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                  {openAlerts > 99 ? '99+' : openAlerts}
                </span>
              )}
            </NavLink>

            <div className="relative">
              <button
                type="button"
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100"
                onClick={() => setMenuOpen((open) => !open)}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                  {user?.full_name?.[0]?.toUpperCase() ?? 'U'}
                </span>
                <span className="hidden text-left sm:block">
                  <span className="block text-sm font-medium leading-tight text-slate-900">
                    {user?.full_name}
                  </span>
                  <span className="block text-[11px] capitalize leading-tight text-slate-500">
                    {user?.role}
                  </span>
                </span>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </button>

              {menuOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden />
                  <div className="absolute right-0 z-20 mt-1 w-52 rounded-lg border border-surface-border bg-white py-1 shadow-raised">
                    <div className="border-b border-surface-border px-3 py-2">
                      <p className="truncate text-sm font-medium text-slate-900">{user?.full_name}</p>
                      <p className="truncate text-xs text-slate-500">{user?.email}</p>
                    </div>
                    <NavLink
                      to="/settings"
                      className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      onClick={() => setMenuOpen(false)}
                    >
                      Settings
                    </NavLink>
                    <button
                      type="button"
                      onClick={logout}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                    >
                      <LogOut className="h-4 w-4" />
                      Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        <main className="p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
