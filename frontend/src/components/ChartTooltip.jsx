import { fmtMW, fmtSigned, fmtUTC } from '../lib/format.js';

/** Shared tooltip for the time-series charts. `rows` maps dataKey -> label/color. */
export default function ChartTooltip({ active, payload, rows }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="t">{fmtUTC(d.t)}</div>
      {rows.map(({ key, label, color, signed }) =>
        d[key] === null || d[key] === undefined ? null : (
          <div className="row" key={key}>
            <span className="k">{color && <i style={{ background: color }} />}{label}</span>
            <span>{signed ? fmtSigned(d[key]) : fmtMW(d[key])}</span>
          </div>
        ),
      )}
      {d.lead_h !== null && d.lead_h !== undefined && (
        <div className="row"><span className="k">Forecast lead</span><span>{d.lead_h} h</span></div>
      )}
    </div>
  );
}
