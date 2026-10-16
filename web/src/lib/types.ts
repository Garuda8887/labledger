export type Sex = "male" | "female" | "other" | "unspecified";
export type Flag = "low" | "high" | "normal" | "unknown";
export type Status = "normal" | "borderline" | "out" | "unknown";

export interface Profile {
  id: string;
  display_name: string;
  dob: string | null;
  sex: Sex | string;
  preferred_unit_system: "conventional" | "si" | string;
  created_at: string;
}

export interface Doc {
  id: string;
  profile_id: string;
  original_filename: string;
  mime: string;
  source_type: string;
  page_count: number;
  lab_name: string | null;
  report_date: string | null;
  collected_at: string | null;
  status: "processing" | "needs_review" | "confirmed" | "failed";
  uploaded_at: string;
}

export interface Result {
  id: string;
  document_id: string;
  profile_id: string;
  page: number;
  bbox: number[] | null;
  raw_test_name: string;
  raw_value: string;
  raw_unit: string | null;
  raw_ref_text: string | null;
  biomarker_id: string | null;
  comparator: "=" | "<" | ">" | "<=" | ">=";
  value_numeric: number | null;
  value_qualitative: string | null;
  normalized_value: number | null;
  canonical_unit: string | null;
  ref_low: number | null;
  ref_high: number | null;
  ref_source: "report" | "builtin" | null;
  flag: Flag;
  collected_at: string | null;
  confidence: number;
  confidence_reasons: string[];
  status: "pending_review" | "confirmed" | "rejected";
  reviewed_at?: string | null;
}

export interface Biomarker {
  id: string;
  key?: string;
  display_name: string;
  category: string;
  canonical_unit: string;
  decimals: number;
  aliases?: string[];
  /** optional alternate (SI/conventional) display unit + multiply factor from canonical */
  alt_unit?: string | null;
  alt_factor?: number | null;
}
