import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { isDemo, setDemo } from "@/lib/api";
import { initials } from "@/lib/format";
import { useApp } from "@/lib/store";

const NAV: [string, string][] = [["/", "Overview"], ["/analysis", "Analysis"], ["/matrix", "Matrix"], ["/compare", "Compare"], ["/documents", "Documents"], ["/print", "Export"]];

export function Avatar({ name, active, size = 32 }: { name: string; active?: boolean; size?: number }) {
  let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360;
  return (
    <span className={`inline-grid shrink-0 place-items-center rounded-full font-semibold tracking-tight ring-2 transition ${active ? "ring-accent" : "ring-transparent"}`}
      style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${h} 45% 50% / .18)`, color: `hsl(${h} 60% 62%)` }}>{initials(name)}</span>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useApp();
  const next = { system: "dark", dark: "light", light: "system" } as const;
  const icon = { system: "◐", dark: "☾", light: "☀" }[theme];
  return <button onClick={() => setTheme(next[theme])} className="grid h-8 w-8 place-items-center rounded-lg border border-hairline text-sm text-ink-muted hover:text-ink focus-ring" aria-label={`Theme: ${theme}. Switch to ${next[theme]}`} title={`Theme: ${theme}`}>{icon}</button>;
}

function ProfileSwitch() {
  const { profiles, profile, setProfileId } = useApp();
  const nav = useNavigate();
  if (!profiles?.length) return null;
  return (
    <div className="flex items-center -space-x-1.5">
      {profiles.slice(0, 4).map((p) => (
        <button key={p.id} onClick={() => setProfileId(p.id)} className="rounded-full focus-ring" aria-pressed={p.id === profile?.id} title={p.display_name}>
          <Avatar name={p.display_name} active={p.id === profile?.id} />
        </button>
      ))}
      <button onClick={() => nav("/profiles")} className="ml-2.5 grid h-8 w-8 place-items-center rounded-full border border-dashed border-hairline text-ink-muted hover:text-ink focus-ring" aria-label="Manage profiles">+</button>
    </div>
  );
}

export default function Layout() {
  const link = ({ isActive }: { isActive: boolean }) => `rounded-lg px-3 py-1.5 text-sm transition-colors focus-ring ${isActive ? "bg-surface-overlay text-ink" : "text-ink-muted hover:text-ink"}`;
  return (
    <div className="flex min-h-screen flex-col [overflow-x:clip]">
      <header className="no-print sticky top-0 z-30 border-b border-hairline/70 bg-surface/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 focus-ring rounded-lg">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <span className="hidden text-lg font-semibold tracking-tight min-[380px]:inline">Labledger</span>
          </NavLink>
          <nav className="hidden gap-1 md:flex" aria-label="Main">{NAV.map(([to, l]) => <NavLink key={to} to={to} end={to === "/"} className={link}>{l}</NavLink>)}</nav>
          <div className="ml-auto flex items-center gap-3">
            {isDemo() && <button onClick={() => setDemo(false)} className="rounded-full bg-status-borderline/15 px-2 py-0.5 text-[11px] text-status-borderline" title="Exit demo data">Demo</button>}
            <ProfileSwitch />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-6 sm:px-6 md:pb-12 md:pt-10">
        <Outlet />
      </main>
      <footer className="no-print border-t border-hairline/60 px-4 py-6 pb-24 text-center text-xs text-ink-subtle md:pb-6">
        Labledger organizes your reports for reference. It is informational and not medical advice.
      </footer>
      <nav className="no-print fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-hairline/70 bg-surface/85 backdrop-blur-xl md:hidden" aria-label="Main mobile">
        {NAV.map(([to, l]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `py-3 text-center text-[11px] ${isActive ? "text-accent" : "text-ink-muted"}`}>{l}</NavLink>)}
      </nav>
    </div>
  );
}
