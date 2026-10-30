import { useEffect, useState } from 'react';
import {
  Area, ComposedChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api } from '../lib/api.js';
import { addDays, fmtMW, fmtSigned, fmtTime, fmtUTC, fmtPct } from '../lib/format.js';
import ChartTooltip from './ChartTooltip.jsx';
import StatTile from './StatTile.jsx';

const TOOLTIP_ROWS = [
  { key: 'forecast', label: 'Forecast at decision', color: 'var(--forecast)' },
  { key: 'actual', label: 'Actual', color: 'var(--actual)' },
  { key: 'band_low', label: 'Band low (P10)' },
  { key: 'band_high', label: 'Band high (P90)' },
  { key: 'error', label: 'Error (fc − act)', signed: true },
];

/**
 * "What did we know when we bought?" One delivery day, one decision moment on D-1,
 * the forecast that existed at that moment, and (in hindsight) what happened.
 */
export default function DecisionView({ meta }) {
  const [day, setDay] = useState('2026-01-15');
  const [clock, setClock] = useState(meta.default_decision_time);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.decision(day, clock)
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [day, clock]);

  const first = meta.delivery_days.first;
  const last = meta.delivery_days.last;
  const h = data?.hindsight;
  const fs = data?.forecast_summary;
  const hasActuals = h && h.n > 0;
  // Energy = mean MW over 48 half-hours * 24 h.
  const forecastGWh = fs?.mean_mw != null ? (fs.mean_mw * 24) / 1000 : null;
  const actualGWh = h?.mean_actual_mw != null ? (h.mean_actual_mw * 24) / 1000 : null;

  return (
    <>
      <div className="controls">
        <div className="control">
          <label htmlFor="day">Delivery day</label>
          <input id="day" type="date" min={first} max={last} value={day}
            onChange={(e) => e.target.value && setDay(e.target.value)} />
          <span className="hint">Decisions made in Jan 2026 → delivery {first} to {last}</span>
        </div>
        <div className="control">
          <label htmlFor="clock">Decision time on D-1 (UTC)</label>
          <input id="clock" type="time" value={clock} step="900" onChange={(e) => setClock(e.target.value)} />
          <span className="hint">GB day-ahead auction gate closes mid-morning</span>
        </div>
        <div className="control">
          <label>Navigate</label>
          <div className="btn-row">
            <button className="btn" disabled={day <= first} onClick={() => setDay(addDays(day, -1))}>← Prev day</button>
            <button className="btn" disabled={day >= last} onClick={() => setDay(addDays(day, 1))}>Next day →</button>
          </div>
        </div>
      </div>

      {error && <div className="state error">{error}</div>}
      {!data && !error && <div className="state">Loading…</div>}

      {data && (
        <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}>
          <div className="callout">
            <strong>Decision at {fmtUTC(data.decision_time)}</strong> — latest wind forecast run available was published{' '}
            <strong>{fmtUTC(data.forecast_run_used)}</strong>
            {fs?.n_points ? (
              <> and expected <strong>{fmtMW(fs.mean_mw)}</strong> on average across the day
                (range {fmtMW(fs.min_mw)} – {fmtMW(fs.max_mw)}; ≈ {forecastGWh.toFixed(1)} GWh).</>
            ) : <>; no forecast covered this day at that time.</>}
            {hasActuals && (
              <span className="muted">
                In hindsight the day delivered {fmtMW(h.mean_actual_mw)} on average (≈ {actualGWh.toFixed(1)} GWh):
                forecast was {h.bias_mw > 0 ? 'too high' : 'too low'} by {fmtMW(Math.abs(h.bias_mw))} on average.
                Shaded band = P10–P90 of past January error at the same lead time (empirical, not a model).
              </span>
            )}
          </div>

          <div className="grid cols-4">
            <StatTile label="Forecast energy (day)" value={forecastGWh != null ? `${forecastGWh.toFixed(1)} GWh` : '–'}
              note="Sum of the forecast at decision time" />
            <StatTile label="Actual energy (day)" value={actualGWh != null ? `${actualGWh.toFixed(1)} GWh` : '–'}
              note="Known only after delivery" />
            <StatTile label="Day bias" value={hasActuals ? fmtSigned(h.bias_mw) : '–'}
              note="+ = over-forecast (had to buy more)" />
            <StatTile label="Day MAE" value={hasActuals ? fmtMW(h.mae_mw) : '–'}
              note={hasActuals ? `${fmtPct(h.nmae_pct)} of mean output` : ''} />
          </div>

          <div className="card">
            <h2>Forecast available at decision time vs actual</h2>
            <p className="sub">Delivery day {data.delivery_day}, half-hourly, UTC. Hover for details.</p>
            <div className="legend">
              <span><i className="sw" style={{ background: 'var(--forecast)' }} />Forecast at decision</span>
              <span><i className="sw" style={{ background: 'var(--actual)' }} />Actual</span>
              <span><i className="sw band" style={{ background: 'var(--band)' }} />P10–P90 error band</span>
            </div>
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={data.series} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="t" tickFormatter={fmtTime} interval={5} tick={{ fontSize: 12, fill: 'var(--text-3)' }}
                  axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
                <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} width={52} tick={{ fontSize: 12, fill: 'var(--text-3)' }}
                  axisLine={false} tickLine={false} label={{ value: 'MW', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'var(--text-3)', dx: 4 }} />
                <Tooltip content={<ChartTooltip rows={TOOLTIP_ROWS} />} />
                {/* Range area: dataKey returns [low, high] so only the band is shaded. */}
                <Area dataKey={(d) => (d.band_low == null ? null : [d.band_low, d.band_high])}
                  stroke="none" fill="var(--band)" fillOpacity={0.16} isAnimationActive={false} connectNulls />
                <Line dataKey="forecast" stroke="var(--forecast)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
                <Line dataKey="actual" stroke="var(--actual)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <details>
            <summary>Half-hourly table ({data.series.length} rows)</summary>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Time (UTC)</th><th>Forecast</th><th>Actual</th><th>Error</th><th>Lead (h)</th><th>Forecast published</th></tr></thead>
                <tbody>
                  {data.series.map((r) => (
                    <tr key={r.t}>
                      <td>{fmtTime(r.t)}</td><td>{fmtMW(r.forecast)}</td><td>{fmtMW(r.actual)}</td>
                      <td>{fmtSigned(r.error)}</td><td>{r.lead_h ?? '–'}</td><td>{fmtUTC(r.publish_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </>
  );
}