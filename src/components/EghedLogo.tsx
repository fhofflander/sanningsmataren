// Eghed logo. Bundled as an imported asset (Vite fingerprints it into each build
// target) - never hotlinked, so the extension's CSP and offline use both work.
import eghedLogo from "../assets/eghed-logo-black.svg";

export function EghedLogo({ className = "" }: { className?: string }) {
  return (
    <a
      href="https://eghed.se/"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="eghed"
      className={className}
    >
      {/* viewBox 283.5 x 78.7 (~3.6:1) */}
      <img src={eghedLogo} alt="eghed" className="h-full w-auto" />
    </a>
  );
}
