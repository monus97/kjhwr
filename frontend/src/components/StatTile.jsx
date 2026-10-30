export default function StatTile({ label, value, note }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="num">{value}</div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}
