// AltCtrl wordmark, rendered as inline JSX (not an image) so it stays crisp and
// needs no asset. "alt_" in ink, "ctrl" + trailing "_" in the brand green.
export function AltCtrlWordmark({ className = "" }: { className?: string }) {
  return (
    <a
      href="https://alltunderkontroll.se"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="alt_ctrl_ (alltunderkontroll AB)"
      className={`font-mono font-bold tracking-tight text-brand-altctrl-ink no-underline ${className}`}
    >
      alt_<span className="text-brand-altctrl">ctrl_</span>
    </a>
  );
}
