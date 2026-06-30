interface Props {
  done: number;
  total: number;
  message?: string | null;
}

export function StatusLine({ done, total, message }: Props) {
  if (total === 0 && !message) return null;

  const hasProgress = total > 0;
  const complete = hasProgress && done >= total;
  const pct = hasProgress ? Math.round((done / total) * 100) : 35;
  const label =
    message ??
    (complete
      ? `Klart - ${total} påståenden granskade`
      : `Granskar ${done} av ${total}...`);

  return (
    <div role="status" aria-live="polite" aria-atomic="true">
      <div
        className="mb-1.5 h-1 w-full overflow-hidden rounded-full bg-line"
        aria-hidden
      >
        <div
          className={`h-full rounded-full bg-accent transition-all duration-300 ${
            hasProgress ? "" : "animate-pulse"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="font-mono text-xs uppercase tracking-widest text-ink-muted">
        {label}
      </p>
    </div>
  );
}
