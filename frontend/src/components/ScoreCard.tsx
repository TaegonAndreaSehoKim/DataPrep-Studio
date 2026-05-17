export function ScoreCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="score-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
