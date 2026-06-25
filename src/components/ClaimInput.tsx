import { useEffect, useState } from "react";

const EXAMPLES: { label: string; text: string }[] = [
  {
    label: "Elpriser & skatt",
    text: "Sverige har EU:s högsta elpriser och regeringen har sänkt skatten mest för de som tjänar allra mest.",
  },
  {
    label: "Arbetslöshet",
    text: "Sedan regeringsskiftet 2022 har arbetslösheten i Sverige minskat kraftigt.",
  },
  {
    label: "Riksdagsomröstning",
    text: "Vänsterpartiet röstade emot den svenska Natoansökan i riksdagen.",
  },
];

interface Props {
  onSubmit: (text: string) => void;
  busy: boolean;
  initialText?: string;
}

export function ClaimInput({ onSubmit, busy, initialText = "" }: Props) {
  const [text, setText] = useState("");

  useEffect(() => {
    if (initialText) setText(initialText);
  }, [initialText]);

  const submit = () => {
    if (text.trim().length > 0 && !busy) onSubmit(text.trim());
  };

  return (
    <section className="space-y-3">
      <label htmlFor="sm-claim-input" className="sr-only">
        Text att faktagranska
      </label>
      <textarea
        id="sm-claim-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Klistra in ett citat, ett inlägg, en artikel eller ett debattutdrag..."
        rows={6}
        className="w-full resize-y rounded-lg border border-line-strong bg-surface p-4 text-[15px] leading-relaxed shadow-sm focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/40"
      />

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={submit}
          disabled={busy || text.trim().length === 0}
          aria-busy={busy}
          className="rounded-md bg-accent px-5 py-2.5 font-mono text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Granskar..." : "Granska"}
        </button>

        <span className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
          Exempel:
        </span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            onClick={() => setText(ex.text)}
            disabled={busy}
            className="min-h-9 rounded-full border border-line px-3 py-1.5 font-mono text-[11px] text-ink-muted hover:border-accent hover:text-accent disabled:opacity-40"
          >
            {ex.label}
          </button>
        ))}
      </div>
    </section>
  );
}
