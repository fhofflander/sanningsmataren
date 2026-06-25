import { useEffect, useState } from "react";
import { COST_MODE_LABELS, PROVIDER_LABELS } from "../lib/providers";
import type { CostMode, ProviderId, Settings as SettingsType } from "../lib/types";

interface Props {
  settings: SettingsType;
  onSave: (next: SettingsType) => void;
  onClear: () => void;
}

export function Settings({ settings, onSave, onClear }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<SettingsType>(settings);
  const [saved, setSaved] = useState(false);

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
    setDraft((d) => ({ ...d, geminiKey: "", anthropicKey: "" }));
    setSaved(false);
  };

  const keyField =
    draft.provider === "anthropic" ? "anthropicKey" : "geminiKey";
  const keyValue = draft[keyField];
  const keyLink =
    draft.provider === "anthropic"
      ? "https://console.anthropic.com/"
      : "https://aistudio.google.com/apikey";

  return (
    <section className="rounded-xl border border-slate-200 bg-surface shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-3 text-left"
      >
        <span className="font-mono text-xs uppercase tracking-widest text-slate-600">
          Inställningar / API-nyckel
        </span>
        <span className="font-mono text-xs text-slate-400">
          {open ? "dölj" : "visa"}
        </span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-slate-100 px-5 py-4">
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-slate-500">
              Leverantör
            </label>
            <div className="flex gap-2">
              {(Object.keys(PROVIDER_LABELS) as ProviderId[]).map((id) => (
                <button
                  key={id}
                  onClick={() => update({ provider: id })}
                  className={`rounded-md border px-3 py-1.5 font-mono text-xs ${
                    draft.provider === id
                      ? "border-accent bg-accent-soft text-accent-deep"
                      : "border-slate-200 text-slate-600 hover:border-slate-300"
                  }`}
                >
                  {PROVIDER_LABELS[id]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-slate-500">
              Körläge
            </label>
            <div className="flex gap-2">
              {(Object.keys(COST_MODE_LABELS) as CostMode[]).map((id) => (
                <button
                  key={id}
                  onClick={() => update({ costMode: id })}
                  className={`rounded-md border px-3 py-1.5 font-mono text-xs ${
                    draft.costMode === id
                      ? "border-accent bg-accent-soft text-accent-deep"
                      : "border-slate-200 text-slate-600 hover:border-slate-300"
                  }`}
                >
                  {COST_MODE_LABELS[id]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-slate-500">
              API-nyckel ({PROVIDER_LABELS[draft.provider]})
            </label>
            <input
              type="password"
              value={keyValue}
              onChange={(e) =>
                update(
                  draft.provider === "anthropic"
                    ? { anthropicKey: e.target.value }
                    : { geminiKey: e.target.value },
                )
              }
              placeholder={draft.provider === "anthropic" ? "sk-ant-..." : "AIza... / AQ..."}
              autoComplete="off"
              spellCheck={false}
              className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm focus:border-accent focus:outline-none"
            />
            <p className="mt-1 font-mono text-[10px] text-slate-400">
              Hämta nyckel:{" "}
              <a
                href={keyLink}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent underline"
              >
                {keyLink}
              </a>
            </p>
          </div>

          <p className="rounded-md bg-surface-muted px-3 py-2 text-xs leading-relaxed text-slate-600">
            Nyckeln sparas endast lokalt i din webbläsare (localStorage) och
            skickas bara direkt till {PROVIDER_LABELS[draft.provider]}. Den når
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
              className="rounded-md border border-slate-300 px-4 py-2 font-mono text-xs uppercase tracking-wide text-slate-600 hover:border-slate-400"
            >
              Rensa nycklar
            </button>
            {saved && (
              <span className="font-mono text-xs text-green-700">Sparat ✓</span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
