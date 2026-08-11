import { isStaticWebsiteOnly } from "../static-mode";

import { buildLoginUrl } from "./types";

let unauthorizedHandling: Promise<void> | null = null;

export function isMockAPIRequest(input: RequestInfo | URL | string): boolean {
  const url =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.toString()
        : input.url;
  try {
    const origin =
      typeof window === "undefined"
        ? "http://localhost"
        : window.location.origin;
    return new URL(url, origin).pathname.startsWith("/mock/api/");
  } catch {
    return false;
  }
}

/** Clear an expired HttpOnly session before sending the browser to login. */
export function handleUnauthorized(returnPath?: string): Promise<void> {
  if (
    typeof window === "undefined" ||
    isStaticWebsiteOnly() ||
    window.location.pathname.startsWith("/login")
  ) {
    return Promise.resolve();
  }

  if (!unauthorizedHandling) {
    const nextPath = returnPath ?? window.location.pathname;
    unauthorizedHandling = (async () => {
      try {
        await globalThis.fetch("/api/v1/auth/logout", {
          method: "POST",
          credentials: "include",
          keepalive: true,
        });
      } catch {
        // Navigation still gives the user a recoverable path when logout fails.
      }
      window.location.assign(buildLoginUrl(nextPath));
    })();
  }

  return unauthorizedHandling;
}
