// Fetch helpers for the admin API. Same-origin: the session cookie is
// HttpOnly and handled entirely by the browser.

import type { GranskningDoc } from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly errors: string[] = []
  ) {
    super(message);
  }
}

interface ErrorEnvelope {
  message?: string;
  errors?: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Kunde inte nå servern.");
  }
  const body = (await res.json().catch(() => null)) as (T & ErrorEnvelope) | null;
  if (!res.ok) {
    throw new ApiError(body?.message ?? `Fel ${res.status}.`, body?.errors ?? []);
  }
  if (body === null) throw new ApiError("Tomt svar från servern.");
  return body;
}

function postInit(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  };
}

export async function fetchMe(): Promise<string | null> {
  try {
    const r = await request<{ username: string }>("/api/admin/me");
    return r.username;
  } catch {
    return null;
  }
}

export function login(username: string, password: string): Promise<{ username: string }> {
  return request("/api/admin/login", postInit({ username, password }));
}

export function logout(): Promise<{ ok: boolean }> {
  return request("/api/admin/logout", postInit({}));
}

export function requestUploadUrl(debateId: string): Promise<{ url: string; key: string }> {
  return request("/api/admin/upload-url", postInit({ debateId }));
}

export interface PublishResult {
  ok: boolean;
  id: string;
  warnings: string[];
  videoUrl: string | null;
  republished: boolean;
}

export function publish(granskning: GranskningDoc, andringsnot: string): Promise<PublishResult> {
  return request(
    "/api/admin/publish",
    postInit({ granskning, andringsnot: andringsnot.trim() || undefined })
  );
}

export function uploadVideo(
  url: string,
  file: File,
  onProgress: (fraction: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError(`Uppladdningen misslyckades (${xhr.status}).`));
    xhr.onerror = () => reject(new ApiError("Uppladdningen misslyckades (nätverksfel)."));
    xhr.send(file);
  });
}
