"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError, AskResult, Health, HistoryItem } from "./api";

type Ctx = {
  health: Health | null;
  healthError: string | null;
  history: HistoryItem[];
  result: AskResult | null;
  loading: boolean;
  error: string | null;
  ask: (q: string) => Promise<void>;
  openHistory: (id: string) => Promise<void>;
  clear: () => void;
};

const AppCtx = createContext<Ctx | null>(null);
export const useApp = () => {
  const c = useContext(AppCtx);
  if (!c) throw new Error("useApp outside provider");
  return c;
};

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    try { setHistory(await api.history()); } catch { /* sidebar is best-effort */ }
  }, []);

  useEffect(() => {
    api.health().then((h) => { setHealth(h); setHealthError(null); }).catch((e: Error) => setHealthError(e.message));
    refreshHistory();
  }, [refreshHistory]);

  const ask = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.ask(q));
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
      refreshHistory();
    }
  }, [refreshHistory]);

  const openHistory = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try { setResult(await api.historyItem(id)); } catch (e) { setError(e instanceof Error ? e.message : "Failed to load"); } finally { setLoading(false); }
  }, []);

  const clear = useCallback(() => { setResult(null); setError(null); }, []);

  const value = useMemo(() => ({ health, healthError, history, result, loading, error, ask, openHistory, clear }),
    [health, healthError, history, result, loading, error, ask, openHistory, clear]);
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}
