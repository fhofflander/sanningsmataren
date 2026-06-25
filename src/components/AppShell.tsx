import type { ReactNode } from "react";
import { BrandLockup } from "./BrandLockup";
import { Footer } from "./Footer";

interface Props {
  variant: "web" | "extension";
  // Variant-specific header subtitle: the intro lede (web) or source line (ext).
  subtitle?: ReactNode;
  children: ReactNode;
}

// Single owner of the page chrome (container, header, co-branding, footer) so the
// web app and the extension side panel share one source of truth.
export function AppShell({ variant, subtitle, children }: Props) {
  const isExt = variant === "extension";

  return (
    <div
      className={`mx-auto flex flex-col px-4 ${
        isExt ? "min-h-screen max-w-xl py-5" : "min-h-full max-w-3xl py-8 sm:py-12"
      }`}
    >
      <header className={isExt ? "mb-5" : "mb-8"}>
        <h1
          className={`font-mono font-bold tracking-tight text-accent-deep ${
            isExt ? "text-xl" : "text-2xl sm:text-3xl"
          }`}
        >
          Sanningsmätaren
        </h1>
        {subtitle}
        <div className="mt-3">
          <BrandLockup compact={isExt} />
        </div>
      </header>

      <div className="space-y-6">{children}</div>

      {!isExt && (
        <>
          <div className="flex-1" />
          <Footer />
        </>
      )}
    </div>
  );
}
