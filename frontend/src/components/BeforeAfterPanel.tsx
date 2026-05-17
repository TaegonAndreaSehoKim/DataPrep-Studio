export function BeforeAfterPanel({
  before,
  after
}: {
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}) {
  return (
    <div className="before-after">
      <pre>{JSON.stringify(before, null, 2)}</pre>
      <pre>{JSON.stringify(after, null, 2)}</pre>
    </div>
  );
}
