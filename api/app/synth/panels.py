"""Fictional analyte panels and ground-truth row builders. No real PHI."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class TruthRow:
    """One ground-truth result row for accuracy eval."""

    biomarker_key: str
    raw_test_name: str
    raw_value: str
    raw_unit: str | None
    raw_ref_text: str | None
    value_numeric: float | None
    value_qualitative: str | None = None
    comparator: str = "="
    flag: Literal["low", "high", "normal", "unknown"] = "normal"
    ref_low: float | None = None
    ref_high: float | None = None
    printed_flag: str | None = None  # H / L / None
    section: str | None = None
    page: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Canonical display names / units for Indian-style reports (fictional wording).
# Aliases chosen to exercise matching, not to copy any real lab brand.

def _cbc(sex: str = "male") -> list[TruthRow]:
    hb_lo, hb_hi = (13.0, 17.0) if sex == "male" else (12.0, 15.0)
    return [
        TruthRow("hemoglobin", "Hemoglobin", "14.2", "g/dL", f"{hb_lo} - {hb_hi}", 14.2, flag="normal", ref_low=hb_lo, ref_high=hb_hi, section="COMPLETE BLOOD COUNT"),
        TruthRow("rbc", "RBC Count", "4.85", "mill/cumm", "4.5 - 5.5", 4.85, flag="normal", ref_low=4.5, ref_high=5.5, section="COMPLETE BLOOD COUNT"),
        TruthRow("wbc", "Total Leucocyte Count", "7200", "/cumm", "4000 - 11000", 7200, flag="normal", ref_low=4000, ref_high=11000, section="COMPLETE BLOOD COUNT"),
        TruthRow("platelets", "Platelet Count", "2.45", "Lakhs/cumm", "1.5 - 4.5", 2.45, flag="normal", ref_low=1.5, ref_high=4.5, section="COMPLETE BLOOD COUNT"),
        TruthRow("hematocrit", "PCV", "42.5", "%", "40 - 50", 42.5, flag="normal", ref_low=40, ref_high=50, section="COMPLETE BLOOD COUNT"),
        TruthRow("mcv", "MCV", "87.6", "fL", "83 - 101", 87.6, flag="normal", ref_low=83, ref_high=101, section="COMPLETE BLOOD COUNT"),
        TruthRow("mch", "MCH", "29.3", "pg", "27 - 32", 29.3, flag="normal", ref_low=27, ref_high=32, section="COMPLETE BLOOD COUNT"),
        TruthRow("mchc", "MCHC", "33.4", "Gms%", "31.5 - 34.5", 33.4, flag="normal", ref_low=31.5, ref_high=34.5, section="COMPLETE BLOOD COUNT"),
        TruthRow("neutrophils_pct", "Neutrophils", "58", "%", "40 - 70", 58, flag="normal", ref_low=40, ref_high=70, section="DIFFERENTIAL COUNT"),
        TruthRow("lymphocytes_pct", "Lymphocytes", "32", "%", "20 - 40", 32, flag="normal", ref_low=20, ref_high=40, section="DIFFERENTIAL COUNT"),
        TruthRow("monocytes_pct", "Monocytes", "6", "%", "2 - 10", 6, flag="normal", ref_low=2, ref_high=10, section="DIFFERENTIAL COUNT"),
        TruthRow("eosinophils_pct", "Eosinophils", "3", "%", "1 - 6", 3, flag="normal", ref_low=1, ref_high=6, section="DIFFERENTIAL COUNT"),
        TruthRow("basophils_pct", "Basophils", "1", "%", "0 - 2", 1, flag="normal", ref_low=0, ref_high=2, section="DIFFERENTIAL COUNT"),
    ]


def _lipids(ldl: float = 118.0) -> list[TruthRow]:
    flag = "high" if ldl >= 130 else ("normal" if ldl < 100 else "normal")
    # NCEP: desirable LDL <100, but many Indian labs use <130 as reference
    printed = "H" if ldl >= 130 else None
    return [
        TruthRow("total_cholesterol", "Cholesterol - Total", "198", "mg/dL", "Desirable < 200\nBorderline 200-239\nHigh >= 240", 198.0, flag="normal", ref_low=None, ref_high=200, section="LIPID PROFILE"),
        TruthRow("ldl", "LDL Cholesterol", f"{ldl:.0f}", "mg/dL", "< 130", ldl, flag="high" if ldl >= 130 else "normal", ref_low=None, ref_high=130, printed_flag=printed, section="LIPID PROFILE"),
        TruthRow("hdl", "HDL Cholesterol", "48", "mg/dL", "> 40", 48.0, flag="normal", ref_low=40, ref_high=None, section="LIPID PROFILE"),
        TruthRow("triglycerides", "Triglycerides", "142", "mg/dL", "< 150", 142.0, flag="normal", ref_low=None, ref_high=150, section="LIPID PROFILE"),
        TruthRow("vldl", "VLDL", "28", "mg/dL", "5 - 40", 28.0, flag="normal", ref_low=5, ref_high=40, section="LIPID PROFILE"),
    ]


def _liver() -> list[TruthRow]:
    return [
        TruthRow("sgot", "SGOT (AST)", "28", "U/L", "Up to 40", 28.0, flag="normal", ref_low=None, ref_high=40, section="LIVER FUNCTION"),
        TruthRow("sgpt", "SGPT (ALT)", "32", "U/L", "Up to 41", 32.0, flag="normal", ref_low=None, ref_high=41, section="LIVER FUNCTION"),
        TruthRow("alp", "Alkaline Phosphatase", "78", "U/L", "40 - 129", 78.0, flag="normal", ref_low=40, ref_high=129, section="LIVER FUNCTION"),
        TruthRow("ggt", "GGT", "24", "U/L", "< 55", 24.0, flag="normal", ref_low=None, ref_high=55, section="LIVER FUNCTION"),
        TruthRow("bilirubin_total", "Bilirubin Total", "0.7", "mg/dL", "0.3 - 1.2", 0.7, flag="normal", ref_low=0.3, ref_high=1.2, section="LIVER FUNCTION"),
        TruthRow("albumin", "Albumin", "4.2", "g/dL", "3.5 - 5.2", 4.2, flag="normal", ref_low=3.5, ref_high=5.2, section="LIVER FUNCTION"),
    ]


def _kidney() -> list[TruthRow]:
    return [
        TruthRow("urea", "Blood Urea", "28", "mg/dL", "17 - 43", 28.0, flag="normal", ref_low=17, ref_high=43, section="KIDNEY FUNCTION"),
        TruthRow("creatinine", "Serum Creatinine", "0.9", "mg/dL", "0.7 - 1.3", 0.9, flag="normal", ref_low=0.7, ref_high=1.3, section="KIDNEY FUNCTION"),
        TruthRow("uric_acid", "Uric Acid", "5.4", "mg/dL", "3.5 - 7.2", 5.4, flag="normal", ref_low=3.5, ref_high=7.2, section="KIDNEY FUNCTION"),
        TruthRow("sodium", "Sodium", "140", "mEq/L", "136 - 145", 140.0, flag="normal", ref_low=136, ref_high=145, section="ELECTROLYTES"),
        TruthRow("potassium", "Potassium", "4.2", "mEq/L", "3.5 - 5.1", 4.2, flag="normal", ref_low=3.5, ref_high=5.1, section="ELECTROLYTES"),
    ]


def _thyroid() -> list[TruthRow]:
    return [
        TruthRow("tsh", "TSH", "2.15", "µIU/mL", "0.4 - 4.2", 2.15, flag="normal", ref_low=0.4, ref_high=4.2, section="THYROID"),
        TruthRow("t3", "Total T3", "112", "ng/dL", "80 - 200", 112.0, flag="normal", ref_low=80, ref_high=200, section="THYROID"),
        TruthRow("t4", "Total T4", "7.8", "µg/dL", "5.1 - 14.1", 7.8, flag="normal", ref_low=5.1, ref_high=14.1, section="THYROID"),
        TruthRow("free_t4", "Free T4", "1.15", "ng/dL", "0.8 - 1.8", 1.15, flag="normal", ref_low=0.8, ref_high=1.8, section="THYROID"),
    ]


def _diabetes() -> list[TruthRow]:
    return [
        TruthRow("glucose_fasting", "Fasting Blood Sugar", "98", "mg/dL", "70 - 100", 98.0, flag="normal", ref_low=70, ref_high=100, section="DIABETES"),
        TruthRow("hba1c", "HbA1c", "5.4", "%", "4.0 - 5.6", 5.4, flag="normal", ref_low=4.0, ref_high=5.6, section="DIABETES"),
    ]


def _vitamins(vit_d: float = 28.0) -> list[TruthRow]:
    flag: Literal["low", "high", "normal", "unknown"] = "low" if vit_d < 30 else "normal"
    return [
        TruthRow("vitamin_d", "25-OH Vitamin D", f"{vit_d:.1f}", "ng/mL", "30 - 100", vit_d, flag=flag, ref_low=30, ref_high=100, printed_flag="L" if flag == "low" else None, section="VITAMINS & IRON"),
        TruthRow("vitamin_b12", "Vitamin B12", "420", "pg/mL", "200 - 900", 420.0, flag="normal", ref_low=200, ref_high=900, section="VITAMINS & IRON"),
        TruthRow("ferritin", "Ferritin", "85", "ng/mL", "30 - 400", 85.0, flag="normal", ref_low=30, ref_high=400, section="VITAMINS & IRON"),
        TruthRow("iron", "Serum Iron", "95", "µg/dL", "60 - 170", 95.0, flag="normal", ref_low=60, ref_high=170, section="VITAMINS & IRON"),
    ]


def _inflammation(crp: float = 1.2) -> list[TruthRow]:
    flag: Literal["low", "high", "normal", "unknown"] = "high" if crp > 3.0 else "normal"
    return [
        TruthRow("crp", "C-Reactive Protein", f"{crp:.1f}", "mg/L", "< 3.0", crp, flag=flag, ref_low=None, ref_high=3.0, printed_flag="H" if flag == "high" else None, section="INFLAMMATION"),
        TruthRow("esr", "ESR", "12", "mm/hr", "0 - 20", 12.0, flag="normal", ref_low=0, ref_high=20, section="INFLAMMATION"),
    ]


def _comparators() -> list[TruthRow]:
    return [
        TruthRow("psa", "PSA Total", "<0.5", "ng/mL", "< 4.0", 0.5, comparator="<", flag="normal", ref_low=None, ref_high=4.0, section="TUMOR MARKERS"),
        TruthRow("troponin_i", "Troponin I", "<0.01", "ng/mL", "< 0.04", 0.01, comparator="<", flag="normal", ref_low=None, ref_high=0.04, section="CARDIAC"),
    ]


def _qualitative() -> list[TruthRow]:
    return [
        TruthRow("urine_protein", "Urine Protein", "Negative", None, "Negative", None, value_qualitative="Negative", flag="normal", section="URINE ROUTINE"),
        TruthRow("urine_glucose", "Urine Glucose", "Nil", None, "Nil", None, value_qualitative="Nil", flag="normal", section="URINE ROUTINE"),
        TruthRow("hbsag", "HBsAg", "Non-reactive", None, "Non-reactive", None, value_qualitative="Non-reactive", flag="normal", section="SEROLOGY"),
    ]


def _sex_specific_ranges(sex: str = "male") -> list[TruthRow]:
    """Printed as Male: x-y / Female: x-y on the report."""
    if sex == "female":
        return [
            TruthRow(
                "hemoglobin",
                "Hemoglobin",
                "12.8",
                "g/dL",
                "Male: 13.0 - 17.0 / Female: 12.0 - 15.0",
                12.8,
                flag="normal",
                ref_low=12.0,
                ref_high=15.0,
                section="CBC",
            ),
            TruthRow(
                "creatinine",
                "Creatinine",
                "0.75",
                "mg/dL",
                "Male: 0.7 - 1.3 / Female: 0.6 - 1.1",
                0.75,
                flag="normal",
                ref_low=0.6,
                ref_high=1.1,
                section="KFT",
            ),
        ]
    return [
        TruthRow(
            "hemoglobin",
            "Hemoglobin",
            "15.1",
            "g/dL",
            "Male: 13.0 - 17.0 / Female: 12.0 - 15.0",
            15.1,
            flag="normal",
            ref_low=13.0,
            ref_high=17.0,
            section="CBC",
        ),
        TruthRow(
            "creatinine",
            "Creatinine",
            "1.05",
            "mg/dL",
            "Male: 0.7 - 1.3 / Female: 0.6 - 1.1",
            1.05,
            flag="normal",
            ref_low=0.7,
            ref_high=1.3,
            section="KFT",
        ),
    ]


def _si_mixed() -> list[TruthRow]:
    """Mixed conventional + SI on one report."""
    return [
        TruthRow("glucose_fasting", "Fasting Glucose", "5.4", "mmol/L", "3.9 - 5.6", 5.4, flag="normal", ref_low=3.9, ref_high=5.6, section="CHEMISTRY"),
        TruthRow("total_cholesterol", "Cholesterol", "5.12", "mmol/L", "< 5.2", 5.12, flag="normal", ref_low=None, ref_high=5.2, section="CHEMISTRY"),
        TruthRow("creatinine", "Creatinine", "88", "µmol/L", "62 - 115", 88.0, flag="normal", ref_low=62, ref_high=115, section="CHEMISTRY"),
        TruthRow("hemoglobin", "Haemoglobin", "142", "g/L", "130 - 170", 142.0, flag="normal", ref_low=130, ref_high=170, section="HAEMATOLOGY"),
    ]


@dataclass
class PanelSpec:
    name: str
    rows: list[TruthRow] = field(default_factory=list)


def build_full_panel(
    *,
    sex: str = "male",
    ldl: float = 118.0,
    vit_d: float = 28.0,
    crp: float = 1.2,
    include_comparators: bool = False,
    include_qualitative: bool = False,
    include_si: bool = False,
    sex_specific: bool = False,
) -> list[TruthRow]:
    rows: list[TruthRow] = []
    if sex_specific:
        rows.extend(_sex_specific_ranges(sex))
    else:
        rows.extend(_cbc(sex))
    rows.extend(_lipids(ldl))
    rows.extend(_liver())
    rows.extend(_kidney())
    rows.extend(_thyroid())
    rows.extend(_diabetes())
    rows.extend(_vitamins(vit_d))
    rows.extend(_inflammation(crp))
    if include_comparators:
        rows.extend(_comparators())
    if include_qualitative:
        rows.extend(_qualitative())
    if include_si:
        rows.extend(_si_mixed())
    return rows


def slim_panel(keys: list[str], base: list[TruthRow] | None = None) -> list[TruthRow]:
    base = base or build_full_panel()
    wanted = set(keys)
    return [r for r in base if r.biomarker_key in wanted]
