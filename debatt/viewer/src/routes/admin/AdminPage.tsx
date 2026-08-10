// Admin: sign in, load granskning.json, upload video, preview, publish.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { compileTimeline } from "../../../../format/src/compile";
import { validateGranskning } from "../../../../format/src/validate";
import type { GranskningDoc, Timeline } from "../../types";
import { DebateView } from "../../components/DebateView";
import {
  ApiError,
  fetchMe,
  login,
  logout,
  publish,
  requestUploadUrl,
  uploadVideo,
  type PublishResult,
} from "../../lib/adminApi";
import { usePlaybackLocalUrl } from "../useLocalFileUrl";

function LoginForm({ onSignedIn }: { onSignedIn: (username: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    login(username, password)
      .then((r) => onSignedIn(r.username))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false));
  };

  return (
    <form className="admin-login" onSubmit={submit}>
      <h2>Logga in</h2>
      <label>
        Användarnamn
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
      </label>
      <label>
        Lösenord
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {error && <p className="admin-error">{error}</p>}
      <button className="play-button" type="submit" disabled={busy}>
        {busy ? "Loggar in ..." : "Logga in"}
      </button>
    </form>
  );
}

type UploadState =
  | { phase: "idle" }
  | { phase: "uploading"; fraction: number }
  | { phase: "done" }
  | { phase: "error"; message: string };

function Workflow({ username, onSignedOut }: { username: string; onSignedOut: () => void }) {
  const [doc, setDoc] = useState<GranskningDoc | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const { url: localVideoUrl, loadFile: loadLocalVideo } = usePlaybackLocalUrl();
  const [upload, setUpload] = useState<UploadState>({ phase: "idle" });
  const [andringsnot, setAndringsnot] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string[] | null>(null);
  const [result, setResult] = useState<PublishResult | null>(null);

  const loadGranskningFile = (file: File) => {
    void file.text().then((text) => {
      setDoc(null);
      setTimeline(null);
      setErrors([]);
      setWarnings([]);
      setUpload({ phase: "idle" });
      setResult(null);
      setPublishError(null);
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        setErrors(["Filen är inte giltig JSON."]);
        return;
      }
      const found = validateGranskning(parsed);
      setWarnings(found.warnings);
      if (found.errors.length > 0) {
        setErrors(found.errors);
        return;
      }
      const granskning = parsed as GranskningDoc;
      setDoc(granskning);
      setTimeline(compileTimeline(granskning, { generatedAt: new Date().toISOString() }));
    });
  };

  const startUpload = () => {
    if (!doc || !videoFile) return;
    setUpload({ phase: "uploading", fraction: 0 });
    requestUploadUrl(doc.debate.id)
      .then(({ url }) =>
        uploadVideo(url, videoFile, (fraction) => setUpload({ phase: "uploading", fraction }))
      )
      .then(() => setUpload({ phase: "done" }))
      .catch((e) =>
        setUpload({ phase: "error", message: e instanceof Error ? e.message : String(e) })
      );
  };

  const doPublish = () => {
    if (!doc) return;
    setPublishing(true);
    setPublishError(null);
    setResult(null);
    publish(doc, andringsnot)
      .then(setResult)
      .catch((e) => {
        if (e instanceof ApiError && e.errors.length > 0) setPublishError([e.message, ...e.errors]);
        else setPublishError([e instanceof Error ? e.message : String(e)]);
      })
      .finally(() => setPublishing(false));
  };

  const hosted = doc?.debate.video.mode === "hosted";
  const videoReady = !hosted || upload.phase === "done";

  return (
    <>
      <div className="admin-bar">
        <span>
          Inloggad som <strong>{username}</strong>
        </span>
        <button
          className="file-button"
          onClick={() => {
            void logout().finally(onSignedOut);
          }}
        >
          Logga ut
        </button>
      </div>

      <section className="granska-panel">
        <h3>1. Ladda granskning.json</h3>
        <label className="file-button">
          Välj fil
          <input
            type="file"
            accept="application/json"
            onChange={(e) => e.target.files?.[0] && loadGranskningFile(e.target.files[0])}
          />
        </label>
        {doc && (
          <p className="admin-loaded">
            Laddad: <strong>{doc.debate.titel}</strong> ({doc.debate.id}, {doc.debate.datum},{" "}
            {doc.events.length} påståenden, video: {doc.debate.video.mode})
          </p>
        )}
        {errors.length > 0 && (
          <div className="granska-findings granska-errors">
            <strong>Fel ({errors.length}) - måste åtgärdas:</strong>
            <ul>
              {errors.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {warnings.length > 0 && (
          <div className="granska-findings granska-warnings">
            <strong>Varningar ({warnings.length}):</strong>
            <ul>
              {warnings.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {doc && hosted && (
        <section className="granska-panel">
          <h3>2. Ladda upp video</h3>
          <p>
            Videon laddas upp direkt till det privata lagringsutrymmet och blir publik först när
            du publicerar.
          </p>
          <div className="header-files">
            <label className="file-button">
              Välj videofil
              <input
                type="file"
                accept="video/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) {
                    setVideoFile(f);
                    loadLocalVideo(f);
                    setUpload({ phase: "idle" });
                  }
                }}
              />
            </label>
            <button
              className="play-button"
              disabled={!videoFile || upload.phase === "uploading" || upload.phase === "done"}
              onClick={startUpload}
            >
              {upload.phase === "done" ? "Uppladdad" : "Ladda upp"}
            </button>
          </div>
          {videoFile && (
            <p className="admin-loaded">
              {videoFile.name} ({(videoFile.size / 1024 / 1024).toFixed(0)} MB)
            </p>
          )}
          {upload.phase === "uploading" && (
            <div className="admin-progress">
              <div className="admin-progress-fill" style={{ width: `${upload.fraction * 100}%` }} />
            </div>
          )}
          {upload.phase === "error" && <p className="admin-error">{upload.message}</p>}
        </section>
      )}

      {timeline && (
        <section className="granska-panel">
          <h3>{hosted ? "3" : "2"}. Förhandsgranska</h3>
          <p>Exakt så här renderas debatten på den publika sidan.</p>
        </section>
      )}
      {timeline && <DebateView timeline={timeline} isDemo={false} localVideoUrl={localVideoUrl} />}

      {timeline && (
        <section className="granska-panel">
          <h3>{hosted ? "4" : "3"}. Publicera</h3>
          <label className="admin-note">
            Ändringsnot (visas i ändringsloggen vid ompublicering)
            <input
              value={andringsnot}
              onChange={(e) => setAndringsnot(e.target.value)}
              placeholder="t.ex. Rättade omdömet för e0004 efter ny källa"
            />
          </label>
          <button
            className="play-button"
            disabled={publishing || !videoReady}
            onClick={doPublish}
          >
            {publishing ? "Publicerar ..." : "Publicera"}
          </button>
          {!videoReady && <p className="admin-error">Ladda upp videon innan du publicerar.</p>}
          {publishError && (
            <div className="granska-findings granska-errors">
              <ul>
                {publishError.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          {result && (
            <div className="granska-findings admin-success">
              <strong>{result.republished ? "Ompublicerad." : "Publicerad."}</strong>{" "}
              <Link to={`/debatt/${result.id}`}>Öppna den publika sidan</Link>
              {result.warnings.length > 0 && (
                <ul>
                  {result.warnings.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}
    </>
  );
}

export function AdminPage() {
  const [state, setState] = useState<
    { phase: "loading" } | { phase: "signed-out" } | { phase: "signed-in"; username: string }
  >({ phase: "loading" });

  useEffect(() => {
    document.title = "Admin - Sanningsmätaren";
    void fetchMe().then((username) =>
      setState(username ? { phase: "signed-in", username } : { phase: "signed-out" })
    );
  }, []);

  if (state.phase === "loading") return <div className="app-loading">Laddar ...</div>;
  if (state.phase === "signed-out") {
    return (
      <main>
        <LoginForm onSignedIn={(username) => setState({ phase: "signed-in", username })} />
      </main>
    );
  }
  return (
    <main>
      <Workflow
        username={state.username}
        onSignedOut={() => setState({ phase: "signed-out" })}
      />
    </main>
  );
}
