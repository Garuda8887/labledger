import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, api } from "./api";
import type { Biomarker, Doc, Profile, Result } from "./types";

type Theme = "system" | "dark" | "light";
/** null = still checking; true = needs unlock; false = open (or lock disabled). */
export type LockState = null | boolean;

interface Ctx {
  profiles: Profile[] | null;
  profile: Profile | null;
  setProfileId: (id: string) => void;
  reloadProfiles: () => Promise<void>;
  theme: Theme;
  setTheme: (t: Theme) => void;
  altUnits: boolean;
  setAltUnits: (b: boolean) => void;
  data: ProfileData | null;
  reloadData: () => void;
  /** true while APP_PASSPHRASE is set and session cookie is missing/invalid */
  needsUnlock: LockState;
  completeUnlock: () => Promise<void>;
}
export interface ProfileData {
  results: Result[]; // confirmed only
  pending: Result[];
  docs: Doc[];
  biomarkers: Map<string, Biomarker>;
}
const AppCtx = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(AppCtx);

function applyTheme(t: Theme) {
  const dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0b0f14" : "#f7f8fa");
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [pid, setPid] = useState<string | null>(() => localStorage.getItem("labledger.profile"));
  const [theme, setThemeS] = useState<Theme>(() => (localStorage.getItem("labledger.theme") as Theme) || "system");
  const [altUnits, setAltS] = useState(() => localStorage.getItem("labledger.alt") === "1");
  const [data, setData] = useState<ProfileData | null>(null);
  const [tick, setTick] = useState(0);
  const [needsUnlock, setNeedsUnlock] = useState<LockState>(null);

  useEffect(() => {
    applyTheme(theme);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => theme === "system" && applyTheme("system");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [theme]);

  const reloadProfiles = useCallback(async () => {
    try {
      setProfiles(await api.profiles());
      setNeedsUnlock(false);
    } catch (e) {
      if (e instanceof ApiError && (e.code === "app_locked" || e.status === 401)) {
        setNeedsUnlock(true);
        setProfiles([]);
        return;
      }
      setProfiles([]);
    }
  }, []);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const st = await api.authStatus();
        if (!live) return;
        if (st.locked && !st.unlocked) {
          setNeedsUnlock(true);
          setProfiles([]);
          return;
        }
        setNeedsUnlock(false);
        await reloadProfiles();
      } catch {
        if (!live) return;
        setNeedsUnlock(false);
        await reloadProfiles();
      }
    })();
    return () => { live = false; };
  }, [reloadProfiles]);

  const completeUnlock = useCallback(async () => {
    setNeedsUnlock(false);
    await reloadProfiles();
  }, [reloadProfiles]);

  const profile = useMemo(() => profiles?.find((p) => p.id === pid) ?? profiles?.[0] ?? null, [profiles, pid]);

  useEffect(() => {
    if (!profile || needsUnlock) { setData(null); return; }
    let live = true;
    setData(null);
    Promise.all([
      api.results({ profile_id: profile.id }).catch(() => []),
      api.documents(profile.id).catch(() => []),
      api.biomarkers().catch(() => []),
    ]).then(([rs, docs, bms]) => {
      if (!live) return;
      const biomarkers = new Map(bms.map((b) => [b.id, b]));
      // also index by key so results referencing either resolve
      bms.forEach((b) => b.key && biomarkers.set(b.key, b));
      setData({
        results: rs.filter((r) => r.status === "confirmed"),
        pending: rs.filter((r) => r.status === "pending_review"),
        docs: docs.sort((a, b) => (b.report_date ?? b.uploaded_at).localeCompare(a.report_date ?? a.uploaded_at)),
        biomarkers,
      });
    });
    return () => { live = false; };
  }, [profile, tick, needsUnlock]);

  const v: Ctx = {
    profiles, profile, reloadProfiles, data,
    setProfileId: (id) => { localStorage.setItem("labledger.profile", id); setPid(id); },
    theme, setTheme: (t) => { localStorage.setItem("labledger.theme", t); setThemeS(t); },
    altUnits, setAltUnits: (b) => { localStorage.setItem("labledger.alt", b ? "1" : "0"); setAltS(b); },
    reloadData: () => setTick((x) => x + 1),
    needsUnlock, completeUnlock,
  };
  return <AppCtx.Provider value={v}>{children}</AppCtx.Provider>;
}

/** Group confirmed numeric results by biomarker, sorted by date. */
export function useSeries(data: ProfileData | null) {
  return useMemo(() => {
    const m = new Map<string, Result[]>();
    data?.results.forEach((r) => { if (r.biomarker_id) (m.get(r.biomarker_id) ?? m.set(r.biomarker_id, []).get(r.biomarker_id)!).push(r); });
    m.forEach((a) => a.sort((x, y) => (x.collected_at ?? "").localeCompare(y.collected_at ?? "")));
    return m;
  }, [data]);
}

export const CATEGORY_ORDER = ["Blood Count", "Lipids", "Liver", "Kidney", "Thyroid", "Diabetes", "Vitamins & Iron", "Hormones", "Electrolytes", "Inflammation", "Urine", "Other"];
export function bmFor(data: ProfileData | null, id: string | null, sample?: Result): Biomarker {
  const b = id ? data?.biomarkers.get(id) : undefined;
  return b ?? { id: id ?? "?", display_name: sample?.raw_test_name ?? id ?? "Unknown", category: "Other", canonical_unit: sample?.canonical_unit ?? sample?.raw_unit ?? "", decimals: 1 };
}
