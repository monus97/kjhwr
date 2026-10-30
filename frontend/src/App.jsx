import { useEffect, useState } from 'react';
import { api } from './lib/api.js';
import { fmtUTC } from './lib/format.js';
import AccuracyView from './components/AccuracyView.jsx';
import DecisionView from './components/DecisionView.jsx';

const TABS = [
  { id: 'decision', label: 'Decision view', title: 'What did we know when we bought?' },
  { id: 'accuracy', label: 'Forecast accuracy', title: 'How much should we trust it?' },
];

export default function App() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('decision');

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="app">
      <header className="top">
        <h1>Wind Forecast Monitor <span>· GB day-ahead · January 2026</span></h1>
        {meta && (
          <div className="meta">
            {meta.n_actuals.toLocaleString()} actuals · {meta.n_forecasts.toLocaleString()} forecast points in {meta.n_forecast_runs} runs
            {' '}· Elexon BMRS (FUELHH, WINDFOR) · data {meta.source}
          </div>
        )}
      </header>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} title={t.title}>
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="state error">
          Could not reach the backend: {error}. Check that the API is running and VITE_API_BASE is set.
        </div>
      )}
      {!meta && !error && <div className="state">Loading dataset…</div>}
      {meta && tab === 'decision' && <DecisionView meta={meta} />}
      {meta && tab === 'accuracy' && <AccuracyView meta={meta} />}

      <footer>
        {meta && <>Actuals {fmtUTC(meta.first_actual)} → {fmtUTC(meta.last_actual)}; forecasts published {fmtUTC(meta.first_publish)} → {fmtUTC(meta.last_publish)}. </>}
        All times UTC (= UK local time in January). Source: Elexon Insights Solution datasets FUELHH (fuelType WIND) and WINDFOR.
      </footer>
    </div>
  );
}
