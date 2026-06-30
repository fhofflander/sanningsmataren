// Calm (non-error) nudge shown before any key is set, so a first-time user is
// guided to add one instead of hitting an error after pressing Granska.
export function KeyNotice({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <div className="rounded-lg border border-accent/30 bg-accent-soft/50 px-4 py-3">
      <p className="text-sm leading-relaxed text-ink">
        För att granska behöver du egna API-nycklar - oftast gratis att skapa
        för lätt användning. Nycklarna sparas bara i din webbläsare och skickas
        direkt till respektive tjänst.
      </p>
      <button
        onClick={onOpenSettings}
        className="mt-2 rounded-md bg-accent px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-wide text-white hover:bg-accent-deep"
      >
        Öppna inställningar
      </button>
    </div>
  );
}
