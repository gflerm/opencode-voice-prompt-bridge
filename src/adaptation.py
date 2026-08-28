"""Correction-based speaker adaptation (spec section 8).

Layers applied around Whisper (the model itself is never retrained):
  1. learned corrections (confirmed review edits, optional context rules)
  2. glossary aliases -> canonical terms (also seeded into initial_prompt)

All replacements are word-boundary exact matches, case-insensitive.
An emergency bypass flag disables learned corrections for one utterance.
"""

from __future__ import annotations

import difflib
import re
import threading

from storage import AdaptationStore


def diff_pairs(original: str, final: str) -> list[tuple[str, str]]:
    """Word-level diff of a user edit: (source words, replacement words).

    Insert-only and delete-only blocks are skipped: a word-boundary
    replacement rule needs evidence on both sides.
    """
    source_words = original.split()
    final_words = final.split()
    matcher = difflib.SequenceMatcher(a=source_words, b=final_words, autojunk=False)
    pairs: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        src = " ".join(source_words[i1:i2])
        rep = " ".join(final_words[j1:j2])
        if src and rep and src.lower() != rep.lower():
            pairs.append((src, rep))
    return pairs


def boundary_pattern(phrase: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)


class AdaptationEngine:
    """Applies stored rules to raw transcripts; never modifies the model."""

    def __init__(self, store: AdaptationStore) -> None:
        self._store = store
        self._lock = threading.Lock()
        self.bypass_next = False
        self.reload()

    def reload(self) -> None:
        with self._lock:
            corrections = self._store.list_corrections(enabled_only=True)
            terms = self._store.list_terms()
            contexts = {c.name: c.keywords for c in self._store.list_contexts()}
        self._rules = sorted(corrections, key=lambda c: len(c.source), reverse=True)
        aliases: list[tuple[str, str]] = []
        self._alias_set: set[str] = set()
        for term in terms:
            for alias in (a.strip() for a in term.aliases.split(",")):
                if not alias:
                    continue
                aliases.append((alias, term.canonical))
                self._alias_set.add(alias.lower())
        self._aliases = sorted(aliases, key=lambda pair: len(pair[0]), reverse=True)
        self._contexts = contexts

    def glossary_initial_prompt(self, max_terms: int = 20) -> str | None:
        """Canonical terms passed to Whisper as decoding context."""
        terms = [t.canonical for t in self._store.list_terms()][:max_terms]
        return ", ".join(terms) if terms else None

    def _context_ok(self, context_name: str, text: str, start: int, end: int, window: int = 80) -> bool:
        keywords = self._contexts.get(context_name, "")
        if not keywords:
            return True
        region = text[max(0, start - window):min(len(text), end + window)].lower()
        return any(k.strip().lower() in region for k in keywords.split(",") if k.strip())

    def apply(self, text: str) -> str:
        """Apply learned corrections then glossary aliases (bypass = skip rules only)."""
        if self.bypass_next:
            self.bypass_next = False
            return text
        for rule in self._rules:
            def replace(match: re.Match, rule=rule) -> str:
                if rule.context and not self._context_ok(rule.context, text, match.start(), match.end()):
                    return match.group(0)
                return rule.replacement
            text = boundary_pattern(rule.source).sub(replace, text)
        for alias, canonical in self._aliases:
            text = boundary_pattern(alias).sub(canonical, text)
        return text

    def learn_pairs(self, pairs: list[tuple[str, str]]) -> int:
        """Store confirmed correction pairs; returns how many were learned."""
        learned = 0
        for src, rep in pairs:
            if src.strip().lower() in self._alias_set:
                continue  # glossary already handles this alias
            self._store.upsert_correction(src, rep)
            learned += 1
        if learned:
            self.reload()
        return learned
