import { Button } from "./Button";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state state-error" role="alert">
    <span>{message}</span>
    {onRetry ? <Button variant="secondary" onClick={onRetry}>Retry</Button> : null}
  </div>;
}
