import { AltCtrlWordmark } from "./AltCtrlWordmark";
import { EghedLogo } from "./EghedLogo";

// The co-branding unit: "Ett samarbete mellan  alt_ctrl_  och  [eghed]".
// `compact` shrinks it for the extension side panel / header endorsement line.
export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
        Ett samarbete mellan
      </span>
      <span className="flex items-center gap-2">
        <AltCtrlWordmark className={compact ? "text-sm" : "text-base"} />
        <span className="text-ink-faint" aria-hidden>
          och
        </span>
        <EghedLogo className={compact ? "inline-block h-3.5" : "inline-block h-5"} />
      </span>
    </div>
  );
}
