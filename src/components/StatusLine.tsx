interface Props {
  done: number;
  total: number;
}

export function StatusLine({ done, total }: Props) {
  if (total === 0) return null;
  const complete = done >= total;
  const pct = Math.round((done / total) * 100);

  return (
    <div role="status" aria-live="polite" aria-atomic="true">
      <div
        className="mb-1.5 h-1 w-full overflow-hidden rounded-full bg-line"
        aria-hidden
      >
        <div
          className="h-full rounded-full bg-accent transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="font-mono text-xs uppercase tracking-widest text-ink-muted">
        {complete
          ? `Klart - ${total} påståenden granskade`
          : `Granskar ${done} av ${total}...`}
      </p>
    </div>
  );
}
