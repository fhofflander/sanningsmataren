// Local preview tool for the editors: load a granskning.json (validated and
// compiled in the browser) or a ready timeline.json, plus a local video
// file, and see exactly what the public page would render. Nothing is
// uploaded; everything stays in the browser.

import { useEffect, useState } from "react";
import type { Timeline } from "../types";
import { compileTimeline } from "../../../format/src/compile";
import { upgradeTimeline } from "../../../format/src/upgrade";
import { validateGranskning } from "../../../format/src/validate";
import { DebateView } from "../components/DebateView";
import { usePlaybackLocalUrl } from "./useLocalFileUrl";

export function GranskaPage() {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const { url: localVideoUrl, loadFile: loadVideoFile } = usePlaybackLocalUrl();

  useEffect(() => {
    document.title = "Förhandsgranska - Sanningsmätaren";
  }, []);

  const loadJsonFile = (file: File) => {
    void file.text().then((text) => {
      setErrors([]);
      setWarnings([]);
      setTimeline(null);
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        setErrors(["Filen är inte giltig JSON."]);
        return;
      }
      const doc = parsed as { formatVersion?: unknown; version?: unknown };
      try {
        if (doc.formatVersion === 1) {
          // granskning.json: validate, show findings, compile if clean.
          const result = validateGranskning(parsed);
          setWarnings(result.warnings);
          if (result.errors.length > 0) {
            setErrors(result.errors);
            return;
          }
          setTimeline(
            compileTimeline(parsed as Parameters<typeof compileTimeline>[0], {
              generatedAt: new Date().toISOString(),
            })
          );
        } else if (typeof doc.version === "number") {
          setTimeline(upgradeTimeline(parsed));
        } else {
          setErrors(["Okänd fil: varken granskning.json (formatVersion 1) eller timeline.json."]);
        }
      } catch (e) {
        setErrors([e instanceof Error ? e.message : String(e)]);
      }
    });
  };

  return (
    <main>
      <div className="granska-panel">
        <p>
          Lokalt förhandsgranskningsverktyg: ladda en <code>granskning.json</code> (valideras och
          kompileras här i webbläsaren) eller en färdig <code>timeline.json</code>, samt en lokal
          videofil. Inget laddas upp.
        </p>
        <div className="header-files">
          <label className="file-button">
            Ladda granskning.json / timeline.json
            <input
              type="file"
              accept="application/json"
              onChange={(e) => e.target.files?.[0] && loadJsonFile(e.target.files[0])}
            />
          </label>
          <label className="file-button">
            Ladda videofil
            <input
              type="file"
              accept="video/*"
              onChange={(e) => e.target.files?.[0] && loadVideoFile(e.target.files[0])}
            />
          </label>
        </div>
        {errors.length > 0 && (
          <div className="granska-findings granska-errors">
            <strong>Fel ({errors.length}) - måste åtgärdas:</strong>
            <ul>
              {errors.map((msg, i) => (
                <li key={i}>{msg}</li>
              ))}
            </ul>
          </div>
        )}
        {warnings.length > 0 && (
          <div className="granska-findings granska-warnings">
            <strong>Varningar ({warnings.length}):</strong>
            <ul>
              {warnings.map((msg, i) => (
                <li key={i}>{msg}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {timeline && <DebateView timeline={timeline} isDemo={false} localVideoUrl={localVideoUrl} />}
    </main>
  );
}
