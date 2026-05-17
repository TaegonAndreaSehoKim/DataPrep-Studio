export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="state">
      <strong>{title}</strong>
      <p>{message}</p>
    </div>
  );
}
