/** The developer server token, taken from the `?token=` the server opens with. */

const STORAGE_KEY = "uipath-dev-token";

let token: string | null = null;

export function initToken(): void {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("token");

  if (fromUrl) {
    token = fromUrl;
    try {
      sessionStorage.setItem(STORAGE_KEY, fromUrl);
    } catch {
      token = fromUrl;
    }
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.toString());
    return;
  }

  try {
    token = sessionStorage.getItem(STORAGE_KEY);
  } catch {
    token = null;
  }
}

export function getToken(): string | null {
  return token;
}

/** Append the token to a WebSocket URL, which cannot carry headers. */
export function withToken(url: string): string {
  const current = getToken();
  if (!current) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(current)}`;
}

/** Send the token on same-origin /api requests. */
export function installAuthenticatedFetch(): void {
  const original = window.fetch.bind(window);

  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const current = getToken();
    if (!current) return original(input, init);

    const raw =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const url = new URL(raw, window.location.href);
    if (url.origin !== window.location.origin || !url.pathname.startsWith("/api")) {
      return original(input, init);
    }

    const headers = new Headers(
      init?.headers ?? (input instanceof Request ? input.headers : undefined),
    );
    if (!headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${current}`);
    }
    return original(input, { ...init, headers });
  };
}
