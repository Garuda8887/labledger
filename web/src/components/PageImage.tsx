import { useEffect, useRef, useState } from "react";
import { bboxToFrac } from "@/lib/bbox";

/** Page PNG with retry while the backend reports page_not_ready (404), plus a scaled bbox overlay. */
export function PageImage({ src, bbox, sourceType, label, fallback }: {
  src: string; bbox?: number[] | null; sourceType: string; label?: string; fallback: React.ReactNode;
}) {
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "waiting" | "failed">("loading");
  const [attempt, setAttempt] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setState("loading"); setAttempt(0); setNat(null); }, [src]);
  useEffect(() => {
    if (state !== "waiting") return;
    const t = setTimeout(() => { setAttempt((a) => a + 1); setState("loading"); }, Math.min(8000, 1000 * 2 ** attempt));
    return () => clearTimeout(t);
  }, [state, attempt]);

  const frac = nat ? bboxToFrac(bbox, sourceType, nat.w, nat.h) : null;
  useEffect(() => { boxRef.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [frac?.top, frac?.left]);

  return (
    <div className="relative">
      {state !== "ok" && (
        <div className="relative">
          {fallback}
          <div className="absolute inset-x-0 top-3 text-center text-xs text-black/60">
            {state === "waiting" ? "Page is still rendering, retrying…" : state === "failed" ? "Page image unavailable" : "Loading page…"}
          </div>
        </div>
      )}
      <img key={`${src}#${attempt}`} src={attempt ? `${src}?r=${attempt}` : src} alt={label ?? "Source page"}
        className={state === "ok" ? "block w-full select-none" : "hidden"} draggable={false}
        onLoad={(e) => { const i = e.currentTarget; setNat({ w: i.naturalWidth, h: i.naturalHeight }); setState("ok"); }}
        onError={() => setState(attempt < 6 ? "waiting" : "failed")} />
      {state === "ok" && frac && (
        <div ref={boxRef} className="pointer-events-none absolute rounded-sm border-2 border-accent bg-accent/15 shadow-[0_0_0_9999px_rgba(0,0,0,0.28)] transition-all duration-200"
          style={{ left: `${frac.left * 100}%`, top: `${frac.top * 100}%`, width: `${frac.width * 100}%`, height: `${frac.height * 100}%` }} />
      )}
    </div>
  );
}
