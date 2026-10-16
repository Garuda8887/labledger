"""Biomarker alias matching: exact → learned → fuzzy (conservative)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from rapidfuzz import fuzz

# Conservative fuzzy threshold (conservative). Below this → unmatched.
FUZZY_THRESHOLD = 90.0


def normalize_name(raw: str | None) -> str:
    if raw is None:
        return ""
    s = unicodedata.normalize("NFKC", str(raw)).strip().lower()
    s = s.replace("µ", "u").replace("μ", "u")
    # Drop parenthetical method noise lightly: keep content but collapse punct
    s = re.sub(r"[^\w\s/%+\-]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass(frozen=True)
class MatchResult:
    biomarker_key: str | None
    biomarker_id: str | None
    method: str  # exact_alias | learned_alias | fuzzy | unmatched
    score: float
    reasons: tuple[str, ...]


@dataclass
class BiomarkerIndex:
    """In-memory index for matching. Pure — no DB dependency."""

    # normalized alias → (canonical_key, biomarker_id or None)
    alias_map: dict[str, tuple[str, str | None]]
    # canonical_key → id
    key_to_id: dict[str, str | None]
    # for fuzzy: list of (normalized_alias, key, id)
    alias_list: list[tuple[str, str, str | None]]

    @classmethod
    def from_biomarkers(
        cls,
        biomarkers: Iterable[dict[str, Any]],
        *,
        learned_aliases: dict[str, str] | None = None,
    ) -> BiomarkerIndex:
        """biomarkers: dicts with canonical_key, aliases, optional id."""
        alias_map: dict[str, tuple[str, str | None]] = {}
        key_to_id: dict[str, str | None] = {}
        alias_list: list[tuple[str, str, str | None]] = []

        for bm in biomarkers:
            key = bm["canonical_key"]
            bid = bm.get("id")
            key_to_id[key] = bid
            names = [bm.get("display_name") or key, key.replace("_", " ")]
            names.extend(bm.get("aliases") or [])
            for name in names:
                n = normalize_name(name)
                if not n:
                    continue
                alias_map[n] = (key, bid)
                alias_list.append((n, key, bid))

        # Learned aliases override / extend (raw_name_normalized → key)
        if learned_aliases:
            for raw_n, key in learned_aliases.items():
                n = normalize_name(raw_n) if raw_n != normalize_name(raw_n) else raw_n
                # learned keys are already normalized per schema
                n = raw_n if raw_n in learned_aliases else normalize_name(raw_n)
                n = normalize_name(raw_n)
                bid = key_to_id.get(key)
                alias_map[n] = (key, bid)

        return cls(alias_map=alias_map, key_to_id=key_to_id, alias_list=alias_list)

    def match(
        self,
        raw_test_name: str,
        *,
        learned_aliases: dict[str, str] | None = None,
    ) -> MatchResult:
        n = normalize_name(raw_test_name)
        if not n:
            return MatchResult(None, None, "unmatched", 0.0, ("empty_name",))

        # Learned first (user overrides)
        if learned_aliases:
            ln = normalize_name(raw_test_name)
            # also try exact key as stored
            for cand in (ln, n):
                if cand in learned_aliases:
                    key = learned_aliases[cand]
                    return MatchResult(
                        key,
                        self.key_to_id.get(key),
                        "learned_alias",
                        1.0,
                        ("learned_alias",),
                    )

        if n in self.alias_map:
            key, bid = self.alias_map[n]
            return MatchResult(key, bid, "exact_alias", 1.0, ("exact_alias",))

        # Fuzzy against alias list
        best_score = 0.0
        best: tuple[str, str | None] | None = None
        for alias, key, bid in self.alias_list:
            score = float(fuzz.token_sort_ratio(n, alias))
            if score > best_score:
                best_score = score
                best = (key, bid)

        if best is not None and best_score >= FUZZY_THRESHOLD:
            return MatchResult(
                best[0],
                best[1],
                "fuzzy",
                best_score / 100.0,
                (f"fuzzy_match:{best_score:.1f}",),
            )

        reasons = ("unmatched",)
        if best is not None:
            reasons = (f"fuzzy_below_threshold:{best_score:.1f}",)
        return MatchResult(None, None, "unmatched", best_score / 100.0, reasons)
