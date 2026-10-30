import { useEffect, useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api } from '../lib/api.js';
import { fmtDay, fmtMW, fmtPct, fmtSigned, fmtTime } from '../lib/format.js';
import ChartTooltip from './ChartTooltip.jsx';
import StatTile from './StatTile.jsx';

const SERIES_ROWS = [
  { key: 'forecast', label: 'Forecast', color: 'var(--forecast)' },
  { key: 'actual', label: 'Actual', color: 'var(--actual)' },
  { key: 'error', label: 'Error (fc − act)', signed: true },
];

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}

function SimpleTip({ active, payload, label, fmt, title }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <div className="t">{title(label, payload[0].payload)}</div>
      {payload.map((p) => (
        <div className="row" key={p.dataKey}><span className="k">{p.name}</span><span>{fmt(p.value)}</span></div>
      ))}
    </div>
  );
}

/**
 * "How much should we trust the forecast?" Pick a window inside January and a
 * horizon H; every target time is matched with the latest forecast published at
 * least H hours before it. Metrics summarise the resulting errors.
 */
export default function AccuracyView({ meta }) {
  const [start, setStart] = useState('2026-01-01');
  const [end, setEnd] = useState('2026-02-01');
  const [horizon, setHorizon] = useState(meta.default_horizon_h);
  const debouncedHorizon = useDebounced(horizon, 150);
  const [data, setData] = useState(null);
  const [curve, setCurve] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const startISO = `${start}T00:00:00Z`;
  const endISO = `${end}T00:00:00Z`;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.accuracy(startISO, endISO, debouncedHorizon)
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [startISO, endISO, debouncedHorizon]);

  useEffect(() => {
    let cancelled = false;
    api.horizonCurve(startISO, endISO).then((d) => { if (!cancelled) setCurve(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, [startISO, endISO]);

  const s = data?.summary;
  const days = useMemo(() => Math.max(1, Math.round((new Date(endISO) - new Date(startISO)) / 864e5)), [startISO, endISO]);
  const xInterval = Math.max(0, Math.floor((data?.series?.length || 0) / 10));

  return (
    <>
      <div className="controls">
        <div className="control">
          <label htmlFor="start">From (delivery)</label>
          <input id="start" type="date" min="2026-01-01" max="2026-02-01" value={start} onChange={(e) => e.target.value && setStart(e.target.value)} />
        </div>
        <div className="control">
          <label htmlFor="end">To (exclusive)</label>
          <input id="end" type="date" min="2026-01-02" max="2026-02-02" value={end} onChange={(e) => e.target.value && setEnd(e.target.value)} />
        </div>
        <div className="control">
          <label htmlFor="h">Forecast horizon: <span className="value">{horizon} h ahead</span></label>
          <input id="h" type="range" min="0" max={meta.max_horizon_h} step="1" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
          <span className="hint">Uses the latest forecast published ≥ {horizon} h before each half-hour. 24 h ≈ day-ahead.</span>
        </div>
        <div className="control">
          <label>Presets</label>
          <div className="btn-row">
            {[6, 12, 24, 36, 48].map((h) => (
              <button key={h} className="btn" onClick={() => setHorizon(h)} aria-pressed={horizon === h}>{h}h</button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="state error">{error}</div>}
      {!data && !error && <div className="state">Loading…</div>}

      {data && s && (
        <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}>
          {s.n > 0 ? (
            <div className="callout">
              At <strong>{data.horizon_h} h ahead</strong>, over {days} day{days > 1 ? 's' : ''} ({s.n} half-hours), the national wind forecast
              missed by <strong>{fmtMW(s.mae_mw)}</strong> on average ({fmtPct(s.nmae_pct)} of mean output of {fmtMW(s.mean_actual_mw)}).
              {' '}On 9 days in 10 the forecast over-estimated wind by less than <strong>{fmtMW(Math.max(0, s.error_p90_mw))}</strong>:
              holding that much extra cover (or an equivalent intraday position) would have covered 90% of shortfalls.
              <span className="muted">
                Bias {fmtSigned(s.bias_mw)} ({s.bias_mw > 0 ? 'forecast tends to run high' : 'forecast tends to run low'});
                {' '}over-forecast in {fmtPct(s.over_forecast_share * 100, 0)} of half-hours; worst miss {fmtMW(s.max_abs_error_mw)}.
              </span>
            </div>
          ) : (
            <div className="state">No half-hours in this window have both an actual and a forecast at this horizon.</div>
          )}

          <div className="grid cols-4">
            <StatTile label="MAE" value={fmtMW(s.mae_mw)} note="Mean absolute error" />
            <StatTile label="RMSE" value={fmtMW(s.rmse_mw)} note="Penalises large misses" />
            <StatTile label="Bias" value={fmtSigned(s.bias_mw)} note="Mean (forecast − actual)" />
            <StatTile label="P90 over-forecast" value={fmtMW(Math.max(0, s.error_p90_mw))} note="90% of shortfalls smaller than this" />
          </div>

          <div className="card">
            <h2>Actual vs forecast ({data.horizon_h} h ahead)</h2>
            <p className="sub">{fmtDay(data.start)} – {fmtDay(data.end)}, half-hourly, UTC.</p>
            <div className="legend">
              <span><i className="sw" style={{ background: 'var(--forecast)' }} />Forecast</span>
              <span><i className="sw" style={{ background: 'var(--actual)' }} />Actual</span>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={data.series} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="t" tickFormatter={days > 2 ? fmtDay : fmtTime} interval={xInterval}
                  tick={{ fontSize: 12, fill: 'var(--text-3)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
                <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} width={52} tick={{ fontSize: 12, fill: 'var(--text-3)' }}
                  axisLine={false} tickLine={false} label={{ value: 'MW', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'var(--text-3)', dx: 4 }} />
                <Tooltip content={<ChartTooltip rows={SERIES_ROWS} />} />
                <Line dataKey="forecast" stroke="var(--forecast)" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                <Line dataKey="actual" stroke="var(--actual)" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid cols-2">
            <div className="card">
              <h2>Error grows with horizon</h2>
              <p className="sub">MAE and P90 over-forecast for each lead time, same window.</p>
              <div className="legend">
                <span><i className="sw" style={{ background: 'var(--actual)' }} />MAE</span>
                <span><i className="sw" style={{ background: 'var(--forecast)' }} />P90 over-forecast</span>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={(curve?.points || []).map((p) => ({ ...p, p90: Math.max(0, p.error_p90_mw ?? 0) }))}
                  margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="horizon_h" tick={{ fontSize: 12, fill: 'var(--text-3)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }}
                    label={{ value: 'hours ahead', position: 'insideBottomRight', fontSize: 11, fill: 'var(--text-3)', dy: 8 }} />
                  <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} width={44} tick={{ fontSize: 12, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<SimpleTip fmt={fmtMW} title={(l) => `${l} h ahead`} />} />
                  <ReferenceLine x={data.horizon_h} stroke="var(--text-3)" strokeDasharray="3 3" />
                  <Line dataKey="mae_mw" name="MAE" stroke="var(--actual)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                  <Line dataKey="p90" name="P90 over-forecast" stroke="var(--forecast)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h2>Bias by hour of day</h2>
              <p className="sub">Mean (forecast − actual) per UTC hour. Above zero = forecast ran high.</p>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={data.by_hour} margin={{ top: 8, right: 16, left: 0, bottom: 0 }} barCategoryGap={2}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 12, fill: 'var(--text-3)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                  <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} width={44} tick={{ fontSize: 12, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<SimpleTip fmt={fmtSigned} title={(l, p) => `${String(l).padStart(2, '0')}:00 UTC · n=${p.n}`} />} cursor={{ fill: 'var(--surface-2)' }} />
                  <ReferenceLine y={0} stroke="var(--text-3)" />
                  <Bar dataKey="bias_mw" name="Bias" fill="var(--actual)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <h2>Error distribution</h2>
            <p className="sub">Count of half-hours by (forecast − actual), 500 MW bins. Right of zero = wind came in below forecast.</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.histogram} margin={{ top: 8, right: 16, left: 0, bottom: 0 }} barCategoryGap={2}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="from_mw" tickFormatter={(v) => `${v / 1000}k`} tick={{ fontSize: 12, fill: 'var(--text-3)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                <YAxis width={44} tick={{ fontSize: 12, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<SimpleTip fmt={(v) => `${v} half-hours`} title={(l, p) => `${fmtSigned(p.from_mw)} to ${fmtSigned(p.to_mw)}`} />} cursor={{ fill: 'var(--surface-2)' }} />
                <ReferenceLine x={0} stroke="var(--text-3)" />
                <Bar dataKey="count" name="Half-hours" fill="var(--actual)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <details>
            <summary>Metric definitions and the data rule</summary>
            <div className="card" style={{ fontSize: 14 }}>
              <p><strong>Pairing rule.</strong> For each half-hour <em>T</em> we take the latest WINDFOR forecast whose
                <code> publishTime ≤ T − horizon</code>. Later forecasts are never used — they were not available when a
                <em> horizon</em>-hours-ahead decision was made.</p>
              <p><strong>Error</strong> = forecast − actual. Positive means less wind arrived than planned (shortfall to cover).</p>
              <p><strong>MAE</strong> average size of the miss. <strong>RMSE</strong> same but large misses weigh more.
                {' '}<strong>Bias</strong> average signed error. <strong>P90 over-forecast</strong> the 90th percentile of the signed error:
                a buffer of this size would have covered 9 in 10 shortfalls. MAPE is deliberately avoided: it explodes in calm periods.</p>
              <p>Median |error| {fmtMW(s.median_abs_error_mw)} · P90 |error| {fmtMW(s.p90_abs_error_mw)} · P10 error {fmtSigned(s.error_p10_mw)} · P50 error {fmtSigned(s.error_p50_mw)}</p>
            </div>
          </details>
        </div>
      )}
    </>
  );
}