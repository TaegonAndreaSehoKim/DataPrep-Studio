export function LoadingState({ message = "Loading" }: { message?: string }) {
  return <div className="state">{message}</div>;
}
