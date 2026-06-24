interface Props {
  done: number;
  total: number;
}

export function StatusLine({ done, total }: Props) {
  if (total === 0) return null;
  const complete = done >= total;
  return (
    <p className="font-mono text-xs uppercase tracking-widest text-slate-500">
      {complete ? `Klart - ${total} påståenden granskade` : `Granskar ${done} av ${total}...`}
    </p>
  );
}
