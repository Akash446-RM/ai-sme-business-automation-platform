import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CHART_COLORS } from '../../utils/constants';
import { formatCurrency, formatNumber, formatShortDate } from '../../utils/format';

const AXIS = { fontSize: 11, fill: '#64748b' };
const GRID = '#eef2f6';

function TooltipBox({ active, payload, label, valueFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-surface-border bg-white px-3 py-2 text-xs shadow-raised">
      <p className="mb-1 font-medium text-slate-900">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} className="flex items-center gap-2 text-slate-600">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: entry.color || entry.fill }}
          />
          <span>{entry.name}:</span>
          <span className="font-medium text-slate-900">
            {valueFormatter ? valueFormatter(entry.value) : formatNumber(entry.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

/** Revenue over time, with an optional forecast overlay. */
export function RevenueTrendChart({ data, height = 280, xKey = 'period', yKey = 'revenue' }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
        <defs>
          <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3366ff" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#3366ff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS} tickFormatter={formatShortDate} tickLine={false} axisLine={false} />
        <YAxis
          tick={AXIS}
          tickFormatter={(value) => formatCurrency(value, { compact: true })}
          tickLine={false}
          axisLine={false}
          width={70}
        />
        <Tooltip content={<TooltipBox valueFormatter={(v) => formatCurrency(v)} />} />
        <Area
          type="monotone"
          dataKey={yKey}
          name="Revenue"
          stroke="#3366ff"
          strokeWidth={2}
          fill="url(#revenueFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Historical actuals followed by predicted values on one axis. */
export function ForecastChart({ data, height = 300 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickFormatter={formatShortDate} tickLine={false} axisLine={false} />
        <YAxis
          tick={AXIS}
          tickFormatter={(value) => formatCurrency(value, { compact: true })}
          tickLine={false}
          axisLine={false}
          width={70}
        />
        <Tooltip content={<TooltipBox valueFormatter={(v) => formatCurrency(v)} />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="actual"
          name="Actual"
          stroke="#64748b"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="predicted"
          name="Forecast"
          stroke="#3366ff"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={{ r: 2 }}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function HorizontalBarChart({ data, xKey, yKey, height = 300, currency = true }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis
          type="number"
          tick={AXIS}
          tickFormatter={(value) =>
            currency ? formatCurrency(value, { compact: true }) : formatNumber(value)
          }
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          type="category"
          dataKey={yKey}
          tick={{ ...AXIS, fontSize: 10 }}
          width={150}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => (value.length > 22 ? `${value.slice(0, 21)}…` : value)}
        />
        <Tooltip
          content={
            <TooltipBox valueFormatter={(v) => (currency ? formatCurrency(v) : formatNumber(v))} />
          }
        />
        <Bar dataKey={xKey} name="Revenue" radius={[0, 4, 4, 0]}>
          {data.map((entry, index) => (
            <Cell key={entry[yKey]} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function VerticalBarChart({ data, xKey, yKey, height = 280, currency = true, name = 'Value' }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis
          tick={AXIS}
          tickFormatter={(value) =>
            currency ? formatCurrency(value, { compact: true }) : formatNumber(value)
          }
          tickLine={false}
          axisLine={false}
          width={currency ? 70 : 45}
        />
        <Tooltip
          content={
            <TooltipBox valueFormatter={(v) => (currency ? formatCurrency(v) : formatNumber(v))} />
          }
        />
        <Bar dataKey={yKey} name={name} fill="#3366ff" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DonutChart({ data, nameKey, valueKey, height = 280, currency = true }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey={valueKey}
          nameKey={nameKey}
          innerRadius="55%"
          outerRadius="80%"
          paddingAngle={2}
        >
          {data.map((entry, index) => (
            <Cell key={entry[nameKey]} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          content={
            <TooltipBox valueFormatter={(v) => (currency ? formatCurrency(v) : formatNumber(v))} />
          }
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
