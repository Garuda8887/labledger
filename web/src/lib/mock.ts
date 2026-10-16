/** Deterministic synthetic demo dataset (fabricated). Used only when demo mode is on. */
import type { Biomarker, Doc, Profile, Result } from "./types";

type Def = [id: string, name: string, cat: string, unit: string, dec: number, lo: number, hi: number, base: number, drift: number, alt?: [string, number]];
const DEFS: Def[] = [
  ["hemoglobin", "Hemoglobin", "Blood Count", "g/dL", 1, 13, 17, 14.6, -0.3, ["g/L", 10]],
  ["wbc", "WBC", "Blood Count", "10³/µL", 1, 4, 11, 6.8, 0.2],
  ["platelets", "Platelets", "Blood Count", "10³/µL", 0, 150, 410, 245, -6],
  ["rbc", "RBC", "Blood Count", "10⁶/µL", 2, 4.5, 5.9, 5.0, -0.05],
  ["mcv", "MCV", "Blood Count", "fL", 1, 80, 100, 88, 0.5],
  ["total_cholesterol", "Total Cholesterol", "Lipids", "mg/dL", 0, 0, 200, 192, 8, ["mmol/L", 0.02586]],
  ["ldl", "LDL Cholesterol", "Lipids", "mg/dL", 0, 0, 130, 118, 7, ["mmol/L", 0.02586]],
  ["hdl", "HDL Cholesterol", "Lipids", "mg/dL", 0, 40, 60, 46, -1.5, ["mmol/L", 0.02586]],
  ["triglycerides", "Triglycerides", "Lipids", "mg/dL", 0, 0, 150, 138, 9, ["mmol/L", 0.01129]],
  ["alt", "ALT (SGPT)", "Liver", "U/L", 0, 7, 56, 32, 3],
  ["ast", "AST (SGOT)", "Liver", "U/L", 0, 10, 40, 27, 1],
  ["bilirubin_total", "Bilirubin, Total", "Liver", "mg/dL", 1, 0.3, 1.2, 0.8, 0.02, ["µmol/L", 17.1]],
  ["creatinine", "Creatinine", "Kidney", "mg/dL", 2, 0.7, 1.3, 1.0, 0.03, ["µmol/L", 88.42]],
  ["urea", "Urea", "Kidney", "mg/dL", 0, 15, 45, 28, 0.5],
  ["egfr", "eGFR", "Kidney", "mL/min/1.73m²", 0, 90, 140, 104, -2],
  ["tsh", "TSH", "Thyroid", "µIU/mL", 2, 0.4, 4.0, 2.4, 0.25],
  ["ft4", "Free T4", "Thyroid", "ng/dL", 2, 0.8, 1.8, 1.2, -0.02],
  ["glucose_fasting", "Glucose, Fasting", "Diabetes", "mg/dL", 0, 70, 100, 94, 2.2, ["mmol/L", 0.0555]],
  ["hba1c", "HbA1c", "Diabetes", "%", 1, 4, 5.6, 5.4, 0.08],
  ["vitamin_d", "Vitamin D (25-OH)", "Vitamins & Iron", "ng/mL", 0, 30, 100, 22, 2.5, ["nmol/L", 2.496]],
  ["vitamin_b12", "Vitamin B12", "Vitamins & Iron", "pg/mL", 0, 200, 900, 310, 15, ["pmol/L", 0.738]],
  ["ferritin", "Ferritin", "Vitamins & Iron", "ng/mL", 0, 30, 400, 85, -3],
  ["testosterone", "Testosterone, Total", "Hormones", "ng/dL", 0, 300, 1000, 520, -12],
];

export const mockBiomarkers: Biomarker[] = DEFS.map(([id, display_name, category, canonical_unit, decimals, , , , , alt]) => ({
  id, key: id, display_name, category, canonical_unit, decimals, aliases: [], alt_unit: alt?.[0] ?? null, alt_factor: alt?.[1] ?? null,
}));

let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

export function buildMock() {
  const profile: Profile = { id: "demo", display_name: "Asha Rao", dob: "1986-04-12", sex: "female", preferred_unit_system: "conventional", created_at: "2023-09-01T00:00:00Z" };
  const labs = ["Metro Diagnostics", "City Path Labs", "Metro Diagnostics", "Apex Labs"];
  const dates = ["2023-10-03", "2024-01-18", "2024-05-02", "2024-09-11", "2025-01-27", "2025-06-09", "2025-11-20", "2026-04-14", "2026-09-30"];
  const docs: Doc[] = [];
  const results: Result[] = [];
  dates.forEach((d, i) => {
    const last = i === dates.length - 1;
    const doc: Doc = {
      id: `doc${i}`, profile_id: "demo", original_filename: `report_${d}.pdf`, mime: "application/pdf", source_type: i % 3 === 1 ? "scanned_pdf" : "digital_pdf",
      page_count: 2, lab_name: labs[i % labs.length]!, report_date: d, collected_at: `${d}T08:30:00Z`, status: last ? "needs_review" : "confirmed", uploaded_at: `${d}T12:00:00Z`,
    };
    docs.push(doc);
    DEFS.forEach(([id, name, , unit, dec, lo, hi, base, drift], j) => {
      if (rnd() < 0.12 && !last) return;
      const shift = doc.lab_name === "Apex Labs" ? 1.05 : 1; // ranges vary by lab
      const v = +(base + drift * i + (rnd() - 0.5) * Math.abs(base) * 0.08).toFixed(dec);
      const rl = lo === 0 ? null : +(lo * shift).toFixed(dec), rh = +(hi * shift).toFixed(dec);
      const flag = rl != null && v < rl ? "low" : v > rh ? "high" : "normal";
      const conf = last ? +(0.45 + rnd() * 0.55).toFixed(2) : 0.97;
      results.push({
        id: `r${i}_${j}`, document_id: doc.id, profile_id: "demo", page: j < 12 ? 1 : 2,
        bbox: [0.08, 0.18 + (j % 12) * 0.06, 0.92, 0.22 + (j % 12) * 0.06],
        raw_test_name: last && j === 4 ? "Mean Corp. Vol" : name.toUpperCase(), raw_value: String(v), raw_unit: unit, raw_ref_text: `${rl ?? "<"} - ${rh}`,
        biomarker_id: last && j === 4 ? null : id, comparator: "=", value_numeric: v, value_qualitative: null, normalized_value: v, canonical_unit: unit,
        ref_low: rl, ref_high: rh, ref_source: "report", flag, collected_at: doc.collected_at, confidence: conf,
        confidence_reasons: conf < 0.7 ? ["low OCR confidence", "unit inferred"] : [], status: last ? "pending_review" : "confirmed",
      });
    });
  });
  // Fabricated duplicate: a second lab's confirmed report collected the same day as the pending
  // report, so ?demo=1 shows the side-by-side conflict panel on the review screen (§6.10).
  const dupDay = dates[dates.length - 1]!;
  docs.push({
    id: "doc_dup", profile_id: "demo", original_filename: `repeat_${dupDay}.pdf`, mime: "application/pdf", source_type: "digital_pdf",
    page_count: 1, lab_name: "City Path Labs", report_date: dupDay, collected_at: `${dupDay}T07:45:00Z`, status: "confirmed", uploaded_at: `${dupDay}T15:00:00Z`,
  });
  (["hemoglobin", "tsh", "vitamin_d"] as const).forEach((bid, k) => {
    const pend = results.find((r) => r.document_id === `doc${dates.length - 1}` && r.biomarker_id === bid);
    const def = DEFS.find((d) => d[0] === bid)!;
    if (!pend || pend.value_numeric == null) return;
    const v = +(pend.value_numeric * (k === 0 ? 1 : k === 1 ? 1.18 : 0.86)).toFixed(def[4]);
    const rl = def[5] === 0 ? null : def[5], rh = def[6];
    results.push({
      ...pend, id: `rdup_${bid}`, document_id: "doc_dup", page: 1, bbox: [0.08, 0.2 + k * 0.06, 0.92, 0.24 + k * 0.06],
      raw_value: String(v), value_numeric: v, normalized_value: v, ref_low: rl, ref_high: rh, raw_ref_text: `${rl ?? "<"} - ${rh}`,
      flag: rl != null && v < rl ? "low" : v > rh ? "high" : "normal", collected_at: `${dupDay}T07:45:00Z`, confidence: 0.97, confidence_reasons: [], status: "confirmed",
    });
  });
  return { profiles: [profile], docs, results };
}
