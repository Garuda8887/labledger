import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar } from "@/components/Layout";
import { Btn, Card, PageTitle, Stagger } from "@/components/ui";
import { api, isDemo, setDemo } from "@/lib/api";
import { useApp } from "@/lib/store";
import type { Sex } from "@/lib/types";

export function Onboarding({ first }: { first?: boolean }) {
  const { reloadProfiles, setProfileId } = useApp();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [sex, setSex] = useState<Sex>("unspecified");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setErr("Please enter a name");
    setBusy(true); setErr(null);
    try {
      const p = await api.createProfile({ display_name: name.trim(), dob: dob || null, sex });
      setProfileId(p.id); await reloadProfiles(); nav("/");
    } catch (e) { setErr((e as Error).message === "404" ? "The API isn't ready to create profiles yet." : (e as Error).message); }
    finally { setBusy(false); }
  }
  const input = "mt-1 w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/30";
  return (
    <Stagger className="mx-auto max-w-md">
      {first && (
        <div className="mb-8 text-center">
          <img src="/favicon.svg" alt="" className="mx-auto mb-4 h-14 w-14" />
          <h1 className="text-3xl font-semibold tracking-tight">Welcome to Labledger</h1>
          <p className="mt-2 text-ink-muted">Your lab reports, organized over time. Everything stays on this machine.</p>
        </div>
      )}
      <Card className="p-6">
        <form onSubmit={submit} className="space-y-4">
          <h2 className="font-semibold">{first ? "Create your profile" : "Add a profile"}</h2>
          <label className="block text-sm text-ink-muted">Name<input className={input} value={name} onChange={(e) => setName(e.target.value)} autoFocus autoComplete="name" /></label>
          <label className="block text-sm text-ink-muted">Date of birth<input type="date" className={input} value={dob} onChange={(e) => setDob(e.target.value)} max={new Date().toISOString().slice(0, 10)} /></label>
          <fieldset>
            <legend className="text-sm text-ink-muted">Sex <span className="text-ink-subtle">(used for reference ranges)</span></legend>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(["female", "male", "other", "unspecified"] as Sex[]).map((s) => (
                <label key={s} className={`cursor-pointer rounded-lg border px-2 py-2 text-center text-sm capitalize transition ${sex === s ? "border-accent bg-accent/10 text-ink" : "border-hairline text-ink-muted"}`}>
                  <input type="radio" name="sex" value={s} checked={sex === s} onChange={() => setSex(s)} className="sr-only" />{s === "unspecified" ? "Prefer not" : s}
                </label>
              ))}
            </div>
          </fieldset>
          {err && <p role="alert" className="text-sm text-status-out">{err}</p>}
          <Btn variant="primary" type="submit" disabled={busy} className="w-full py-2.5">{busy ? "Saving…" : "Continue"}</Btn>
        </form>
      </Card>
      {first && !isDemo() && <p className="mt-6 text-center text-sm text-ink-subtle">Just looking? <button className="text-accent underline-offset-2 hover:underline" onClick={() => setDemo(true)}>Explore with demo data</button></p>}
    </Stagger>
  );
}

export default function Profiles() {
  const { profiles, profile, setProfileId } = useApp();
  const nav = useNavigate();
  return (
    <div>
      <PageTitle title="Profiles" sub="Each person's reports are kept separate." />
      <div className="mb-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {profiles?.map((p, i) => (
          <Stagger key={p.id} i={i}>
            <button onClick={() => { setProfileId(p.id); nav("/"); }} className={`flex w-full items-center gap-3 rounded-card border p-4 text-left transition focus-ring ${p.id === profile?.id ? "border-accent/60 bg-accent/5" : "border-hairline hover:bg-surface-overlay"}`}>
              <Avatar name={p.display_name} size={44} active={p.id === profile?.id} />
              <div><div className="font-medium">{p.display_name}</div><div className="text-xs capitalize text-ink-subtle">{p.sex}{p.dob ? ` · born ${p.dob}` : ""}</div></div>
            </button>
          </Stagger>
        ))}
      </div>
      <Onboarding />
    </div>
  );
}
