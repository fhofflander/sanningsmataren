// Playback clock. Driven by the <video> element when a video source exists
// (hosted URL or locally loaded file), otherwise by an internal timer so a
// timeline can be reviewed without the broadcast file.

import { useCallback, useEffect, useRef, useState } from "react";

export interface Playback {
  time: number;
  playing: boolean;
  usingVideo: boolean;
  videoRef: React.RefObject<HTMLVideoElement>;
  videoUrl: string | null;
  loadVideoFile: (file: File) => void;
  toggle: () => void;
  seek: (t: number) => void;
}

export function usePlayback(durationSec: number, remoteVideoUrl?: string | null): Playback {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [localUrl, setLocalUrl] = useState<string | null>(null);
  const videoUrl = localUrl ?? remoteVideoUrl ?? null;
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timeRef = useRef(0);
  timeRef.current = time;

  // rAF loop: follow the video clock, or advance the demo clock.
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      const video = videoRef.current;
      if (video && videoUrl) {
        setTime(video.currentTime);
      } else if (playing) {
        const next = Math.min(timeRef.current + dt, durationSec || Infinity);
        setTime(next);
        if (durationSec && next >= durationSec) setPlaying(false);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoUrl, playing, durationSec]);

  // Only locally created object URLs are ours to revoke.
  useEffect(() => {
    return () => {
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
  }, [localUrl]);

  const loadVideoFile = useCallback((file: File) => {
    setLocalUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(file);
    });
  }, []);

  const toggle = useCallback(() => {
    const video = videoRef.current;
    if (video && videoUrl) {
      if (video.paused) void video.play();
      else video.pause();
      setPlaying(video.paused === false);
    } else {
      setPlaying((p) => !p);
    }
  }, [videoUrl]);

  const seek = useCallback(
    (t: number) => {
      const video = videoRef.current;
      if (video && videoUrl) video.currentTime = t;
      setTime(t);
    },
    [videoUrl],
  );

  return { time, playing, usingVideo: Boolean(videoUrl), videoRef, videoUrl, loadVideoFile, toggle, seek };
}
