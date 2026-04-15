"""Contextual next-step suggestion builder for tool responses.

Generates 1-3 actionable suggestions based on analysis results,
comparison outcomes, scores, and error codes.  Included in every
tool response to guide the calling LLM toward the optimal next action.

Implements §11.1 of the design specification.
Requirements: FR-TOOL-08, FR-TOOL-10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phraseturner.models.analysis import AnalysisResult, HealthScore
    from phraseturner.models.comparison import ComparisonResult

# Maximum suggestions per response — FR-TOOL-08.
_MAX_STEPS = 3

# Thresholds for next-step suggestion logic.
_COMPLIANCE_THRESHOLD = 0.5
_SIMILARITY_THRESHOLD = 0.7
_IMPROVEMENT_THRESHOLD = 20


class NextStepsBuilder:
    """Generate contextual next-step suggestions for tool responses.

    Each ``for_*`` method inspects the response data and selects from a
    curated suggestion catalog.  All methods return at most 3 strings.

    Implements §11.1.  Requirements: FR-TOOL-08, FR-TOOL-10.
    """

    # ------------------------------------------------------------------
    # analyze tool
    # ------------------------------------------------------------------

    def for_analysis(
        self,
        result: AnalysisResult,
        persona: str | None,
    ) -> list[str]:
        """Generate next steps based on analysis results.

        Args:
            result: The full ``AnalysisResult`` from the pipeline.
            persona: Persona name used for the analysis, if any.

        Returns:
            1-3 contextual suggestion strings.
        """
        steps: list[str] = []
        grade = result.health_score.letter_grade

        if grade in ("D", "F"):
            steps.append(
                "Rewrite the flagged sentences, then call `score` "
                "to verify improvement"
            )

        if (
            persona
            and result.persona_alignment is not None
            and result.persona_alignment.overall_compliance < _COMPLIANCE_THRESHOLD
        ):
            steps.append(
                f"Call `get_persona {persona}` to review tone targets"
            )

        nat_dim = result.health_score.dimensions.get("naturalness")
        if nat_dim is not None and nat_dim.status == "poor":
            steps.append(
                "Vary sentence length and structure to improve naturalness"
            )

        if not steps:
            steps.append(
                "Text quality is good — no immediate action needed"
            )

        return steps[:_MAX_STEPS]

    # ------------------------------------------------------------------
    # compare tool
    # ------------------------------------------------------------------

    def for_comparison(self, result: ComparisonResult) -> list[str]:
        """Generate next steps based on comparison results.

        Args:
            result: The full ``ComparisonResult``.

        Returns:
            1-3 contextual suggestion strings.
        """
        steps: list[str] = []

        if result.overall_improvement < 0:
            steps.append(
                "Rewrite regressed — review the original text's "
                "strengths before rewriting further"
            )

        if result.semantic_similarity < _SIMILARITY_THRESHOLD:
            steps.append(
                "Meaning drift detected — rewrite more conservatively "
                "to preserve core meaning"
            )

        if result.overall_improvement > _IMPROVEMENT_THRESHOLD:
            steps.append(
                "Strong improvement — call `score` on the final "
                "version to confirm"
            )

        if not steps:
            steps.append(
                "Moderate improvement — consider another iteration "
                "targeting the weakest dimension"
            )

        return steps[:_MAX_STEPS]

    # ------------------------------------------------------------------
    # score tool
    # ------------------------------------------------------------------

    def for_score(self, score: HealthScore) -> list[str]:
        """Generate next steps based on quick score.

        Args:
            score: The ``HealthScore`` from the quick-score path.

        Returns:
            1-3 contextual suggestion strings.
        """
        steps: list[str] = []

        if score.letter_grade in ("D", "F"):
            steps.append(
                "Call `analyze` with `include_suggestions=true` "
                "to identify specific issues"
            )
        elif score.letter_grade in ("B", "C"):
            scored_dims = [
                (k, v)
                for k, v in score.dimensions.items()
                if v is not None
            ]
            if scored_dims:
                worst = min(scored_dims, key=lambda x: x[1].score)
                steps.append(
                    f"Weakest dimension is {worst[0]} "
                    f"({worst[1].score:.0f}) — focus rewriting there"
                )

        if not steps:
            steps.append("Score is A — text quality is strong")

        return steps[:_MAX_STEPS]

    # ------------------------------------------------------------------
    # persona tools
    # ------------------------------------------------------------------

    def for_list_personas(self, count: int) -> list[str]:
        """Generate next steps after listing personas.

        Args:
            count: Number of personas returned.

        Returns:
            1-3 contextual suggestion strings.
        """
        if count == 0:
            return [
                "No personas found — call `create_persona` to define one"
            ]
        return [
            "Call `get_persona <name>` to view full details of a persona",
            "Call `analyze` with a persona name to analyse text against it",
        ]

    def for_get_persona(self, name: str) -> list[str]:
        """Generate next steps after retrieving a persona.

        Args:
            name: The persona name that was retrieved.

        Returns:
            1-3 contextual suggestion strings.
        """
        return [
            f"Call `analyze` with `persona=\"{name}\"` to analyse "
            "text against this persona",
            "Call `validate_persona` to check a modified version "
            "before saving",
        ]

    def for_create_persona(self, name: str) -> list[str]:
        """Generate next steps after creating a persona.

        Args:
            name: The name of the newly created persona.

        Returns:
            1-3 contextual suggestion strings.
        """
        return [
            f"Call `analyze` with `persona=\"{name}\"` to test "
            "the new persona",
            f"Call `get_persona {name}` to verify the full definition",
        ]

    def for_validate_persona(self, valid: bool) -> list[str]:
        """Generate next steps after validating a persona.

        Args:
            valid: Whether the persona passed validation.

        Returns:
            1-3 contextual suggestion strings.
        """
        if valid:
            return [
                "Validation passed — call `create_persona` to save it"
            ]
        return [
            "Fix the reported errors and call `validate_persona` again"
        ]

    # ------------------------------------------------------------------
    # error recovery
    # ------------------------------------------------------------------

    def for_error(self, code: str) -> list[str]:
        """Generate recovery suggestions for error responses.

        Args:
            code: Machine-readable error code from the exception.

        Returns:
            1-3 recovery suggestion strings.
        """
        catalog: dict[str, list[str]] = {
            "TEXT_TOO_LONG": [
                "Reduce text to under 8000 tokens, or split into "
                "smaller chunks"
            ],
            "TEXT_TOO_SHORT": [
                "Provide at least one complete sentence for analysis"
            ],
            "PERSONA_NOT_FOUND": [
                "Call `list_personas` to see available personas",
                "Check spelling of the persona name",
            ],
            "PERSONA_EXISTS": [
                "Use a different persona name, or delete the existing "
                "persona first"
            ],
            "PERSONA_VALIDATION_FAILED": [
                "Call `validate_persona` to see specific validation errors"
            ],
        }
        return catalog.get(
            code,
            ["Check the error details and retry with corrected input"],
        )
