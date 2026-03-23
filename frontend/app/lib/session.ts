"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const STORAGE_KEY = "smartpantry.access_token";
const REFRESH_BUFFER_MS = 5 * 60 * 1000;
const INACTIVITY_WINDOW_MS = 30 * 60 * 1000;

type SlidingSessionOptions = {
  apiBase: string;
  onExpired?: () => void;
};

type TokenPayload = {
  exp?: number;
};

function readStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

function writeStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

function decodeTokenPayload(token: string): TokenPayload | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = window.atob(normalized);
    return JSON.parse(json) as TokenPayload;
  } catch {
    return null;
  }
}

export function useSlidingSession({ apiBase, onExpired }: SlidingSessionOptions) {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const lastActivityAtRef = useRef<number>(Date.now());
  const refreshInFlightRef = useRef(false);

  const clearSessionToken = useCallback(() => {
    writeStoredToken(null);
    setToken(null);
  }, []);

  const expireSession = useCallback(() => {
    writeStoredToken(null);
    setToken(null);
    onExpired?.();
  }, [onExpired]);

  const setSessionToken = useCallback((nextToken: string) => {
    writeStoredToken(nextToken);
    setToken(nextToken);
    lastActivityAtRef.current = Date.now();
  }, []);

  useEffect(() => {
    const storedToken = readStoredToken();
    if (storedToken) {
      setToken(storedToken);
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !token) return;

    const recordActivity = () => {
      lastActivityAtRef.current = Date.now();
    };

    const activityEvents: Array<keyof WindowEventMap> = [
      "click",
      "keydown",
      "mousemove",
      "scroll",
      "focus",
    ];

    activityEvents.forEach((eventName) =>
      window.addEventListener(eventName, recordActivity, { passive: true })
    );

    return () => {
      activityEvents.forEach((eventName) =>
        window.removeEventListener(eventName, recordActivity)
      );
    };
  }, [token]);

  const tokenExpMs = useMemo(() => {
    if (!token || typeof window === "undefined") return null;
    const payload = decodeTokenPayload(token);
    return payload?.exp ? payload.exp * 1000 : null;
  }, [token]);

  useEffect(() => {
    if (!token || !tokenExpMs) return;

    const tick = async () => {
      const now = Date.now();
      const inactiveTooLong = now - lastActivityAtRef.current > INACTIVITY_WINDOW_MS;

      if (inactiveTooLong) {
        if (tokenExpMs <= now) {
          expireSession();
        }
        return;
      }

      if (tokenExpMs - now > REFRESH_BUFFER_MS) {
        return;
      }

      if (refreshInFlightRef.current) return;
      refreshInFlightRef.current = true;

      try {
        const res = await fetch(`${apiBase}/auth/refresh`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          expireSession();
          return;
        }

        const payload = (await res.json()) as { access_token?: string };
        if (!payload.access_token) {
          expireSession();
          return;
        }
        setSessionToken(payload.access_token);
      } catch {
        // Keep current token until it actually expires; transient failures should not immediately log users out.
        if (tokenExpMs <= Date.now()) {
          expireSession();
        }
      } finally {
        refreshInFlightRef.current = false;
      }
    };

    const intervalId = window.setInterval(() => {
      void tick();
    }, 60 * 1000);

    void tick();

    return () => window.clearInterval(intervalId);
  }, [apiBase, expireSession, setSessionToken, token, tokenExpMs]);

  return {
    token,
    ready,
    setSessionToken,
    clearSessionToken,
  };
}
