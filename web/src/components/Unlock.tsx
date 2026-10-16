import { useState, type FormEvent } from "react";
import { ApiError, api } from "@/lib/api";
import { Btn, Card } from "./ui";

/** Calm full-screen unlock when APP_PASSPHRASE lock is active. */
export function UnlockScreen({ onUnlocked }: { onUnlocked: () => void | Promise<void> }) {
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!pass.trim()) { setErr("Enter the passphrase"); return; }
    setBusy(true); setErr(null);
    try {
      await api.unlock(pass);
      await onUnlocked();
    } catch (ex) {
      if (ex instanceof ApiError) setErr(ex.message || "Could not unlock");
      else setErr("Could not unlock");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-10">
      <Card className="p-6 sm:p-8">
        <div className="mb-1 text-xs uppercase tracking-[0.14em] text-ink-subtle">Labledger</div>
        <h1 className="text-2xl font-semibold tracking-tight">Unlock</h1>
        <p className="mt-2 text-sm text-ink-muted">
          This app is locked with a passphrase. Enter it to continue — your lab data stays on this device.
        </p>
        <form className="mt-6 space-y-4" onSubmit={(e) => void submit(e)}>
          <label className="block text-xs uppercase tracking-wider text-ink-subtle">
            Passphrase
            <input
              type="password"
              autoFocus
              autoComplete="current-password"
              className="mt-1.5 w-full rounded-lg border border-hairline bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              disabled={busy}
            />
          </label>
          {err && <p role="alert" className="text-sm text-status-out">{err}</p>}
          <Btn type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
            {busy ? "Unlocking…" : "Unlock"}
          </Btn>
        </form>
      </Card>
    </div>
  );
}
