import { BrandLockup } from "./BrandLockup";

export function Footer() {
  return (
    <footer className="mt-12 border-t border-line pt-6 text-xs leading-relaxed text-ink-muted">
      <p>
        Omdömena är automatiskt genererade och kan vara felaktiga. Klicka alltid
        vidare till källorna och bilda dig en egen uppfattning. Verktyget fungerar
        bäst med politikerns exakta ord - ju mer ordagrant påståendet är, desto
        mer träffsäker blir granskningen.
      </p>

      <p className="mt-3">
        Sanningsmätaren är ett oberoende verktyg för faktagranskning av svensk
        politik, utvecklat i samarbete mellan alt_ctrl_ (alltunderkontroll AB) och
        eghed. Sanningsmätaren tar inte partipolitisk ställning - målet är
        transparent och källbaserad granskning.
      </p>

      <div className="mt-5 border-t border-line pt-4">
        <BrandLockup />
        <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
          © 2026 alltunderkontroll AB &amp; eghed · Sanningsmätaren · MIT-licens
        </p>
      </div>
    </footer>
  );
}
