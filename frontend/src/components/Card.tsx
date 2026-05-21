import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  className?: string;
  children: ReactNode;
}

export function Card({ title, className = "", children }: CardProps) {
  return (
    <section className={`card ${className}`.trim()}>
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  );
}
