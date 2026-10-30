export const fmtMW = (v, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '–'
    : `${Number(v).toLocaleString('en-GB', { maximumFractionDigits: digits })} MW`;

export const fmtSigned = (v) =>
  v === null || v === undefined ? '–' : `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString('en-GB')} MW`;

export const fmtPct = (v, digits = 1) =>
  v === null || v === undefined ? '–' : `${Number(v).toFixed(digits)}%`;

const dtf = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
});
export const fmtUTC = (iso) => (iso ? `${dtf.format(new Date(iso))} UTC` : '–');

const tf = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' });
export const fmtTime = (iso) => (iso ? tf.format(new Date(iso)) : '');

const df = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: 'short' });
export const fmtDay = (iso) => (iso ? df.format(new Date(iso)) : '');

export const toISODate = (d) => d.toISOString().slice(0, 10);
export const addDays = (isoDate, n) => {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return toISODate(d);
};
