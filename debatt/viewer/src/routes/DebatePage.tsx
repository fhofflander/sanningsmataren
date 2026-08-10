// Public per-debate page: /debatt/:id

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Timeline } from "../types";
import { DebateView } from "../components/DebateView";
import { fetchIndex, fetchTimeline } from "../lib/data";

export function DebatePage() {
  const { id } = useParams<{ id: string }>();
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTimeline(null);
    setError(null);
    fetchIndex()
      .then((index) => {
        const entry = index.debates.find((d) => d.id === id);
        if (!entry) throw new Error("Debatten hittades inte.");
        setIsDemo(Boolean(entry.demo));
        return fetchTimeline(entry);
      })
      .then((t) => {
        setTimeline(t);
        document.title = `${t.debate.titel} - Sanningsmätaren`;
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  if (error) {
    return (
      <div className="app-error">
        FEL: {error} <Link to="/">Till alla debatter</Link>
      </div>
    );
  }
  if (!timeline) return <div className="app-loading">Laddar debatt ...</div>;

  return <DebateView timeline={timeline} isDemo={isDemo} />;
}
