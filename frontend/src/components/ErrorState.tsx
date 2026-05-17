export function ErrorState({ message }: { message: string }) {
  return <div className="state state-error">{message}</div>;
}
