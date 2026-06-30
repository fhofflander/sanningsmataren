import { useEffect, useState } from "react";
import { COST_MODE_LABELS, PROVIDER_LABELS } from "../lib/providers";
import type { CostMode, ProviderId, Settings as SettingsType } from "../lib/types";

interface Props {
  settings: SettingsType;
  onSave: (next: SettingsType) => void;
  onClear: () => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function Settings({ settings, onSave, onClear, open, onOpenChange }: Props) {
  const [draft, setDraft] = useState<SettingsType>(settings);
  const [saved, setSaved] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  const update = (patch: Partial<SettingsType>) => {
    setDraft((d) => ({ ...d, ...patch }));
    setSaved(false);
  };

  const handleSave = () => {
    onSave(draft);
    setSaved(true);
  };

  const handleClear = () => {
    onClear();
    setDraft((d) => ({
      ...d,
      geminiKey: "",
      anthropicKey: "",
      braveSearchKey: "",
    }));
    setSaved(false);
  };

  const keyValue =
    draft.provider === "anthropic" ? draft.anthropicKey : draft.geminiKey;
  const isAnthropic = draft.provider === "anthropic";
  const usesBudgetSearch = draft.costMode === "budget";
  const keyLink = isAnthropic
    ? "https://console.anthropic.com/"
    : "https://aistudio.google.com/apikey";
  const keyHowto = isAnthropic
    ? "Skapa en nyckel i Anthropic Console (öppnas i ny flik), kopiera och klistra in här."
    : "Skapa en gratis nyckel hos Google AI Studio (öppnas i ny flik) - logga in, klicka Create API key, kopiera och klistra in här.";

  return (
    <section
      className="rounded-lg border border-line bg-surface shadow-sm"
      aria-label="Inställningar och API-nycklar"
    >
      <button
        onClick={() => onOpenChange(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-3 text-left"
      >
        <span className="font-mono text-xs uppercase tracking-widest text-ink-muted">
          Inställningar / API-nycklar
        </span>
        <span
          className="font-mono text-xs text-ink-faint transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
          aria-hidden
        >
          ▸
        </span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-line px-5 py-4">
          <div role="radiogroup" aria-label="Leverantör">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
              Leverantör
            </span>
            <div className="flex gap-2">
              {(Object.keys(PROVIDER_LABELS) as ProviderId[]).map((id) => (
                <button
                  key={id}
                  role="radio"
                  aria-checked={draft.provider === id}
                  onClick={() => update({ provider: id })}
                  className={`min-h-9 rounded-md border px-3 py-1.5 font-mono text-xs ${
                    draft.provider === id
                      ? "border-accent bg-accent-soft text-accent-deep"
                      : "border-line text-ink-muted hover:border-line-strong"
                  }`}
                >
                  {PROVIDER_LABELS[id]}
                </button>
              ))}
            </div>
          </div>

          <div role="radiogroup" aria-label="Körläge">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint">
              Körläge
            </span>
            <div className="flex gap-2">
              {(Object.keys(COST_MODE_LABELS) as CostMode[]).map((id) => (
                <button
                  key={id}
                  role="radio"
                  aria-checked={draft.costMode === id}
                  onClick={() => update({ costMode: id })}
                  className={`min-h-9 rounded-md border px-3 py-1.5 font-mono text-xs ${
                    draft.costMode === id
                      ? "border-accent bg-accent-soft text-accent-deep"
                      : "border-line text-ink-muted hover:border-line-strong"
                  }`}
                >
                  {COST_MODE_LABELS[id]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              htmlFor="sm-api-key"
              className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint"
            >
              API-nyckel ({PROVIDER_LABELS[draft.provider]})
            </label>
            <div className="flex gap-2">
              <input
                id="sm-api-key"
                type={showKey ? "text" : "password"}
                value={keyValue}
                onChange={(e) =>
                  update(
                    isAnthropic
                      ? { anthropicKey: e.target.value }
                      : { geminiKey: e.target.value },
                  )
                }
                placeholder={isAnthropic ? "sk-ant-..." : "AIza... / AQ..."}
                autoComplete="off"
                spellCheck={false}
                className="w-full rounded-md border border-line-strong px-3 py-2 font-mono text-sm focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/40"
              />
              <button
                type="button"
                onClick={() => setShowKey((s) => !s)}
                aria-pressed={showKey}
                className="shrink-0 rounded-md border border-line px-3 font-mono text-xs uppercase tracking-wide text-ink-muted hover:border-line-strong"
              >
                {showKey ? "Dölj" : "Visa"}
              </button>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">
              {keyHowto}{" "}
              <a
                href={keyLink}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-accent underline"
              >
                Öppna sidan
              </a>
            </p>
          </div>

          {usesBudgetSearch && (
            <div>
              <label
                htmlFor="sm-brave-search-key"
                className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink-faint"
              >
                Brave Search API-nyckel (budgetläge)
              </label>
              <div className="flex gap-2">
                <input
                  id="sm-brave-search-key"
                  type={showKey ? "text" : "password"}
                  value={draft.braveSearchKey}
                  onChange={(e) => update({ braveSearchKey: e.target.value })}
                  placeholder="Brave Search API key"
                  autoComplete="off"
                  spellCheck={false}
                  className="w-full rounded-md border border-line-strong px-3 py-2 font-mono text-sm focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/40"
                />
                <a
                  href="https://api-dashboard.search.brave.com/app/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex shrink-0 items-center rounded-md border border-line px-3 font-mono text-xs uppercase tracking-wide text-ink-muted hover:border-line-strong"
                >
                  Hämta
                </a>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">
                Används bara för den billiga webbsökningen i budgetläge.
              </p>
            </div>
          )}

          <p className="rounded-md border-l-2 border-line-strong bg-surface-muted px-3 py-2 text-xs leading-relaxed text-ink-muted">
            Nyckeln sparas endast lokalt i din webbläsare (localStorage) och
            skickas bara direkt till {PROVIDER_LABELS[draft.provider]}
            {usesBudgetSearch ? " och Brave Search" : ""}. Den når
            aldrig någon annan server - appen har ingen backend.
          </p>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              className="rounded-md bg-accent px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wide text-white hover:bg-accent-deep"
            >
              Spara
            </button>
            <button
              onClick={handleClear}
              className="rounded-md border border-line-strong px-4 py-2 font-mono text-xs uppercase tracking-wide text-ink-muted hover:border-ink-faint"
            >
              Rensa nycklar
            </button>
            {saved && (
              <span className="font-mono text-xs text-brand-altctrl">Sparat ✓</span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
