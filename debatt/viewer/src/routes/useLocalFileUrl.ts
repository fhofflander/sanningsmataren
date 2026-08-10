// Object URL for a locally selected file, revoked on replace/unmount.

import { useCallback, useEffect, useState } from "react";

export function usePlaybackLocalUrl() {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  const loadFile = useCallback((file: File) => {
    setUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(file);
    });
  }, []);

  return { url, loadFile };
}
