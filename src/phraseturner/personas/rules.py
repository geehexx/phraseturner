"""Vale-compatible YAML rule parser and evaluator.

Implements section 3.7 of the design specification.
Parses all 10 Vale rule types plus 3 phraseturner extensions.
Supports Vale scope, level, and action systems.

Implements FR-PERSONA-02, FR-PERSONA-08.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import structlog

from phraseturner.personas.schema import RuleType

if TYPE_CHECKING:
    from collections.abc import Callable

    from phraseturner.personas.schema import RuleConfig

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Scope constants -- FR-PERSONA-02 (AC-FR-PERSONA-02.3)
# ---------------------------------------------------------------------------
SCOPE_TEXT = "text"
SCOPE_SENTENCE = "sentence"
SCOPE_PARAGRAPH = "paragraph"
SCOPE_HEADING = "heading"
SCOPE_RAW = "raw"

_VALID_SCOPES = frozenset({SCOPE_TEXT, SCOPE_SENTENCE, SCOPE_PARAGRAPH, SCOPE_HEADING, SCOPE_RAW})

# ---------------------------------------------------------------------------
# Action constants -- FR-PERSONA-02 (AC-FR-PERSONA-02.5)
# ---------------------------------------------------------------------------
ACTION_REPLACE = "replace"
ACTION_EDIT = "edit"
ACTION_REMOVE = "remove"
ACTION_SUGGEST = "suggest"

_VALID_ACTIONS = frozenset({ACTION_REPLACE, ACTION_EDIT, ACTION_REMOVE, ACTION_SUGGEST})

_PARAGRAPH_SEPARATOR = re.compile(r"\n\s*\n")

_METRIC_TRUNCATE_LEN = 50

# Small words exempt from title-case capitalisation
_TITLE_CASE_EXEMPT = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "if",
        "in",
        "nor",
        "of",
        "on",
        "or",
        "so",
        "the",
        "to",
        "up",
        "yet",
    }
)


# ---------------------------------------------------------------------------
# RuleMatch -- structured rule violation result
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RuleMatch:
    """A single rule violation found during evaluation.

    Implements FR-PERSONA-02, FR-PERSONA-08.

    Attributes:
        rule_id: Identifier of the rule that triggered.
        rule_type: The Vale/phraseturner rule type.
        level: Severity level (error, warning, suggestion).
        message: Human-readable description of the violation.
        scope: The scope in which the match was found.
        matched_text: The text fragment that triggered the rule.
        line: 1-based line number of the match.
        col: 1-based column number of the match.
        action: Optional action suggestion (replace, edit, remove, suggest).
        replacement: Optional suggested replacement text.
    """

    rule_id: str
    rule_type: str
    level: str
    message: str
    scope: str
    matched_text: str
    line: int = 1
    col: int = 1
    action: str | None = None
    replacement: str | None = None


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------
def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double-newline boundaries."""
    return [p.strip() for p in _PARAGRAPH_SEPARATOR.split(text) if p.strip()]


def _get_position(text: str, match_start: int) -> tuple[int, int]:
    """Convert a character offset to 1-based (line, col)."""
    prefix = text[:match_start]
    line = prefix.count("\n") + 1
    last_nl = prefix.rfind("\n")
    col = match_start - last_nl if last_nl >= 0 else match_start + 1
    return line, col


def _build_action_info(rule: RuleConfig) -> tuple[str | None, str | None]:
    """Extract action type and replacement from a rule's action dict.

    Implements AC-FR-PERSONA-02.5.
    """
    if rule.action is None:
        return None, None
    action_name = rule.action.get("name")
    params = rule.action.get("params")
    replacement: str | None = None
    if action_name in {ACTION_REPLACE, ACTION_SUGGEST} and isinstance(params, str):
        replacement = params
    return action_name, replacement


def _is_title_case(text: str) -> bool:
    """Check if text follows title case rules.

    First and last words must be capitalised. Small words (articles,
    conjunctions, prepositions) may be lowercase unless they are the
    first or last word.
    """
    words = text.split()
    if not words:
        return True
    for i, word in enumerate(words):
        if i == 0 or i == len(words) - 1:
            if not word[0].isupper():
                return False
        elif word.lower() not in _TITLE_CASE_EXEMPT and not word[0].isupper():
            return False
    return True


# ---------------------------------------------------------------------------
# RuleEvaluator -- dispatches to type-specific handlers
# ---------------------------------------------------------------------------
class RuleEvaluator:
    """Evaluate persona rules against text.

    Dispatches to type-specific handlers based on ``rule.type``.
    Supports all 10 Vale rule types and 3 phraseturner extensions.

    Implements FR-PERSONA-02, FR-PERSONA-08, section 3.7.
    """

    _DISPATCH: ClassVar[dict[str, str]] = {
        RuleType.EXISTENCE: "_eval_existence",
        RuleType.SUBSTITUTION: "_eval_substitution",
        RuleType.OCCURRENCE: "_eval_occurrence",
        RuleType.REPETITION: "_eval_repetition",
        RuleType.CONSISTENCY: "_eval_consistency",
        RuleType.CONDITIONAL: "_eval_conditional",
        RuleType.CAPITALIZATION: "_eval_capitalization",
        RuleType.METRIC: "_eval_metric",
        RuleType.SEQUENCE: "_eval_sequence",
        RuleType.SCRIPT: "_eval_script",
        RuleType.LLM_EVAL: "_eval_llm_eval",
        RuleType.TONE: "_eval_tone",
        RuleType.BRAND_VOICE: "_eval_brand_voice",
    }

    def evaluate(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate a single rule against text.

        Applies scope filtering then dispatches to the type-specific handler.

        Args:
            rule: The rule configuration to evaluate.
            text: The full input text.
            sentences: Pre-split sentences from spaCy.

        Returns:
            List of rule matches (violations) found.
        """
        handler_name = self._DISPATCH.get(rule.type)
        if handler_name is None:
            logger.warning("unknown_rule_type", rule_id=rule.id, rule_type=rule.type)
            return []

        handler = getattr(self, handler_name)
        return self._apply_scope(rule, text, sentences, handler)

    def _apply_scope(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
        handler: Callable[[RuleConfig, str, list[str]], list[RuleMatch]],
    ) -> list[RuleMatch]:
        """Apply scope filtering before calling the handler.

        Implements AC-FR-PERSONA-02.3.

        Args:
            rule: The rule configuration.
            text: Full input text.
            sentences: Pre-split sentences.
            handler: The type-specific evaluation callable.

        Returns:
            Aggregated matches across all scope segments.
        """
        scope = rule.scope if rule.scope in _VALID_SCOPES else SCOPE_TEXT

        if scope in {SCOPE_TEXT, SCOPE_RAW}:
            return handler(rule, text, sentences)
        if scope == SCOPE_SENTENCE:
            matches: list[RuleMatch] = []
            for sent in sentences:
                matches.extend(handler(rule, sent, [sent]))
            return matches
        if scope == SCOPE_PARAGRAPH:
            matches = []
            for para in _split_paragraphs(text):
                para_sents = [s for s in sentences if s in para]
                matches.extend(handler(rule, para, para_sents or [para]))
            return matches
        if scope == SCOPE_HEADING:
            first_line = text.split("\n", maxsplit=1)[0].strip()
            if first_line:
                return handler(rule, first_line, [first_line])
            return []
        return []  # pragma: no cover

    # ------------------------------------------------------------------
    # Vale rule type handlers (1-10)
    # ------------------------------------------------------------------

    def _eval_existence(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate existence rule - regex match on tokens or raw patterns.

        Implements AC-FR-PERSONA-02.1, AC-FR-PERSONA-02.2 (existence).

        Args:
            rule: Rule with ``tokens`` or ``raw`` patterns.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Matches for each pattern occurrence found.
        """
        matches: list[RuleMatch] = []
        action_name, replacement = _build_action_info(rule)
        msg = rule.message or f"Found match for rule '{rule.id}'"

        patterns: list[str] = []
        if rule.tokens:
            patterns = [rf"\b{re.escape(t)}\b" for t in rule.tokens]
        if rule.raw:
            patterns.extend(rule.raw)

        for pattern in patterns:
            try:
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    line, col = _get_position(text, m.start())
                    matches.append(
                        RuleMatch(
                            rule_id=rule.id,
                            rule_type=rule.type,
                            level=rule.level,
                            message=msg,
                            scope=rule.scope,
                            matched_text=m.group(),
                            line=line,
                            col=col,
                            action=action_name,
                            replacement=replacement,
                        )
                    )
            except re.error:
                logger.warning("invalid_regex", rule_id=rule.id, pattern=pattern)
        return matches

    def _eval_substitution(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate substitution rule - regex match with swap suggestion.

        Implements AC-FR-PERSONA-02.1, AC-FR-PERSONA-02.2 (substitution).
        Implements P-rt-03.

        Args:
            rule: Rule with ``swap`` map (pattern to replacement).
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Matches with suggested replacements from the swap map.
        """
        matches: list[RuleMatch] = []
        if not rule.swap:
            return matches

        for pattern, suggestion in rule.swap.items():
            try:
                regex = re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE)
            except re.error:
                logger.warning("invalid_regex", rule_id=rule.id, pattern=pattern)
                continue

            for m in regex.finditer(text):
                line, col = _get_position(text, m.start())
                msg = rule.message or f"Use '{suggestion}' instead of '{m.group()}'"
                matches.append(
                    RuleMatch(
                        rule_id=rule.id,
                        rule_type=rule.type,
                        level=rule.level,
                        message=msg,
                        scope=rule.scope,
                        matched_text=m.group(),
                        line=line,
                        col=col,
                        action=ACTION_REPLACE,
                        replacement=suggestion,
                    )
                )
        return matches

    def _eval_occurrence(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate occurrence rule - count tokens, flag if exceeds max.

        Implements AC-FR-PERSONA-02.1 (occurrence).

        Args:
            rule: Rule with ``tokens`` and ``max`` count.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            A single match if any token exceeds the max occurrence count.
        """
        if not rule.tokens or rule.max is None:
            return []

        matches: list[RuleMatch] = []
        for token in rule.tokens:
            try:
                pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
            except re.error:
                continue
            found = list(pattern.finditer(text))
            if len(found) > rule.max:
                first = found[0]
                line, col = _get_position(text, first.start())
                msg = rule.message or (f"'{token}' occurs {len(found)} times (max {rule.max})")
                matches.append(
                    RuleMatch(
                        rule_id=rule.id,
                        rule_type=rule.type,
                        level=rule.level,
                        message=msg,
                        scope=rule.scope,
                        matched_text=first.group(),
                        line=line,
                        col=col,
                    )
                )
        return matches

    def _eval_repetition(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate repetition rule - detect duplicate words or phrases.

        Implements AC-FR-PERSONA-02.1 (repetition).

        Args:
            rule: Rule configuration (uses ``tokens`` for specific words, or
                detects any repeated words if ``tokens`` is empty).
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Matches for each repeated word/phrase found.
        """
        matches: list[RuleMatch] = []
        words = re.findall(r"\b\w+\b", text.lower())
        seen: dict[str, int] = {}
        targets = {t.lower() for t in rule.tokens} if rule.tokens else None

        for i, word in enumerate(words):
            if targets is not None and word not in targets:
                continue
            if word in seen:
                try:
                    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
                    all_matches = list(pattern.finditer(text))
                    if len(all_matches) > 1:
                        dup = all_matches[1]
                        line, col = _get_position(text, dup.start())
                        msg = rule.message or f"Repeated word: '{word}'"
                        matches.append(
                            RuleMatch(
                                rule_id=rule.id,
                                rule_type=rule.type,
                                level=rule.level,
                                message=msg,
                                scope=rule.scope,
                                matched_text=dup.group(),
                                line=line,
                                col=col,
                            )
                        )
                except re.error:
                    pass
            seen[word] = i
        return matches

    def _eval_consistency(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate consistency rule - enforce either/or word pairs.

        Implements AC-FR-PERSONA-02.1 (consistency).

        When both forms of a pair appear, the less-frequent form is flagged.

        Args:
            rule: Rule with ``either`` map (word_a to word_b).
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Matches for the inconsistent (less-frequent) form.
        """
        if not rule.either:
            return []

        matches: list[RuleMatch] = []

        for word_a, word_b in rule.either.items():
            try:
                regex_a = re.compile(rf"\b{re.escape(word_a)}\b", re.IGNORECASE)
                regex_b = re.compile(rf"\b{re.escape(word_b)}\b", re.IGNORECASE)
            except re.error:
                continue

            hits_a = list(regex_a.finditer(text))
            hits_b = list(regex_b.finditer(text))

            if hits_a and hits_b:
                if len(hits_a) <= len(hits_b):
                    flagged, preferred = hits_a, word_b
                else:
                    flagged, preferred = hits_b, word_a

                for m in flagged:
                    line, col = _get_position(text, m.start())
                    msg = rule.message or (
                        f"Inconsistent usage: use '{preferred}' instead of '{m.group()}'"
                    )
                    matches.append(
                        RuleMatch(
                            rule_id=rule.id,
                            rule_type=rule.type,
                            level=rule.level,
                            message=msg,
                            scope=rule.scope,
                            matched_text=m.group(),
                            line=line,
                            col=col,
                            action=ACTION_REPLACE,
                            replacement=preferred,
                        )
                    )
        return matches

    def _eval_conditional(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate conditional rule - if A present then B must be present.

        Implements AC-FR-PERSONA-02.1 (conditional).

        Uses ``tokens`` as the trigger (A) and ``match`` as the required
        consequent (B). If A is found but B is not, a match is reported.

        Args:
            rule: Rule with ``tokens`` (trigger) and ``match`` (consequent).
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Matches when the trigger is present but the consequent is absent.
        """
        if not rule.tokens or not rule.match:
            return []

        matches: list[RuleMatch] = []

        try:
            consequent_found = bool(re.search(rule.match, text, re.IGNORECASE))
        except re.error:
            return []

        if consequent_found:
            return []

        for token in rule.tokens:
            try:
                pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
            except re.error:
                continue
            for m in pattern.finditer(text):
                line, col = _get_position(text, m.start())
                msg = rule.message or (
                    f"'{m.group()}' found but required term '{rule.match}' is missing"
                )
                matches.append(
                    RuleMatch(
                        rule_id=rule.id,
                        rule_type=rule.type,
                        level=rule.level,
                        message=msg,
                        scope=rule.scope,
                        matched_text=m.group(),
                        line=line,
                        col=col,
                    )
                )
        return matches

    def _eval_capitalization(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate capitalization rule - check heading case patterns.

        Implements AC-FR-PERSONA-02.1 (capitalization).

        Supports ``match`` values: ``$title`` (title case), ``$sentence``
        (sentence case), ``$lower`` (lowercase), ``$upper`` (uppercase).

        Args:
            rule: Rule with ``match`` specifying the expected case pattern.
            text: Text segment to evaluate (typically a heading).
            sentences: Sentences within the segment.

        Returns:
            A single match if the text does not conform to the case pattern.
        """
        if not rule.match:
            return []

        expected = rule.match.strip().lower()
        conforms = True

        if expected == "$title":
            conforms = text == text.title() or _is_title_case(text)
        elif expected == "$sentence":
            conforms = bool(text) and text[0].isupper()
        elif expected == "$lower":
            conforms = text == text.lower()
        elif expected == "$upper":
            conforms = text == text.upper()

        if conforms:
            return []

        msg = rule.message or f"Expected {expected} capitalization"
        return [
            RuleMatch(
                rule_id=rule.id,
                rule_type=rule.type,
                level=rule.level,
                message=msg,
                scope=rule.scope,
                matched_text=text,
                line=1,
                col=1,
            )
        ]

    def _eval_metric(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate metric rule - check readability formula thresholds.

        Implements AC-FR-PERSONA-02.1 (metric).

        Uses ``metric`` field to identify the formula and ``min``/``max``
        fields for thresholds. Requires ``textstat`` for computation.

        Args:
            rule: Rule with ``metric`` name and threshold fields.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            A single match if the metric value falls outside thresholds.
        """
        if not rule.metric:
            return []

        try:
            import textstat  # noqa: PLC0415
        except ImportError:
            logger.warning("textstat_unavailable", rule_id=rule.id)
            return []

        metric_funcs: dict[str, object] = {
            "flesch_reading_ease": textstat.flesch_reading_ease,
            "flesch_kincaid_grade": textstat.flesch_kincaid_grade,
            "gunning_fog": textstat.gunning_fog,
            "coleman_liau_index": textstat.coleman_liau_index,
            "smog_index": textstat.smog_index,
            "ari": textstat.automated_readability_index,
        }

        func = metric_funcs.get(rule.metric)
        if func is None:
            logger.warning("unknown_metric", rule_id=rule.id, metric=rule.metric)
            return []

        value = func(text)  # type: ignore[operator]

        violated = False
        if rule.min is not None and value < rule.min:
            violated = True
        if rule.max is not None and value > rule.max:
            violated = True

        if not violated:
            return []

        msg = rule.message or (
            f"Metric '{rule.metric}' = {value:.1f} (expected min={rule.min}, max={rule.max})"
        )
        truncated = text[:_METRIC_TRUNCATE_LEN]
        if len(text) > _METRIC_TRUNCATE_LEN:
            truncated += "..."
        return [
            RuleMatch(
                rule_id=rule.id,
                rule_type=rule.type,
                level=rule.level,
                message=msg,
                scope=rule.scope,
                matched_text=truncated,
                line=1,
                col=1,
            )
        ]

    def _eval_sequence(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate sequence rule - POS tag sequence matching.

        Implements AC-FR-PERSONA-02.1 (sequence).

        Placeholder: requires spaCy Doc for POS tagging. Returns empty
        until the pipeline provides parsed docs to the evaluator.

        Args:
            rule: Rule with POS sequence pattern.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Empty list (placeholder - needs spaCy Doc integration).
        """
        logger.debug(
            "sequence_rule_placeholder",
            rule_id=rule.id,
            msg="Sequence rules require spaCy Doc - skipped",
        )
        return []

    def _eval_script(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate script rule - EXCLUDED in v1.0.

        Implements NFR-SEC-03.2 (script rules excluded for security).

        Args:
            rule: Rule configuration (ignored).
            text: Text segment (ignored).
            sentences: Sentences (ignored).

        Raises:
            NotImplementedError: Always - script rules are excluded in v1.0.
        """
        raise NotImplementedError(
            f"Script rules are excluded in v1.0 (rule '{rule.id}'). See NFR-SEC-03.2."
        )

    # ------------------------------------------------------------------
    # phraseturner extension handlers (11-13)
    # ------------------------------------------------------------------

    def _eval_llm_eval(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate llm_eval rule - FLAN-T5 prompt evaluation.

        Implements AC-FR-PERSONA-08.1, AC-FR-PERSONA-08.2, AC-FR-PERSONA-08.4.

        Placeholder: returns empty until Phase 4 (T5 integration).
        When Tier < 3, llm_eval rules are skipped per AC-FR-PERSONA-08.4.

        Args:
            rule: Rule with ``prompt``, ``target``, ``tolerance`` fields.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Empty list (placeholder - needs FLAN-T5, Phase 4).
        """
        logger.debug(
            "llm_eval_placeholder",
            rule_id=rule.id,
            msg="llm_eval rules require FLAN-T5 - skipped until Phase 4",
        )
        return []

    def _eval_tone(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate tone rule - dimension threshold check.

        Implements AC-FR-PERSONA-08.1, AC-FR-PERSONA-08.3.

        Placeholder: returns empty until tone analysis is available
        (Phase 3, Stage 1 tone analyser).

        Args:
            rule: Rule with ``dimension``, ``min``, ``max`` fields.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Empty list (placeholder - needs tone analysis, Phase 3).
        """
        logger.debug(
            "tone_rule_placeholder",
            rule_id=rule.id,
            msg="Tone rules require tone analysis - skipped until Phase 3",
        )
        return []

    def _eval_brand_voice(
        self,
        rule: RuleConfig,
        text: str,
        sentences: list[str],
    ) -> list[RuleMatch]:
        """Evaluate brand_voice rule - compliance check.

        Implements AC-FR-PERSONA-08.1.

        Placeholder: returns empty until brand voice analysis is available.

        Args:
            rule: Rule with brand voice compliance criteria.
            text: Text segment to evaluate.
            sentences: Sentences within the segment.

        Returns:
            Empty list (placeholder - needs brand voice analysis).
        """
        logger.debug(
            "brand_voice_placeholder",
            rule_id=rule.id,
            msg="Brand voice rules require brand voice analysis - skipped",
        )
        return []
