"""Tests for the naturalness analyzer (Stage 1).

Validates the ``analyze_naturalness`` function against FR-PIPELINE-04
acceptance criteria.
"""

from __future__ import annotations

from phraseturner.pipeline.naturalness import (
    NaturalnessResult,
    _compute_burstiness,
    _compute_hapax_ratio,
    _compute_length_skewness,
    _compute_punctuation_entropy,
    _compute_starter_diversity,
    _compute_zipf_r_squared,
    _sentence_lengths,
    analyze_naturalness,
)


class TestSentenceLengths:
    """Tests for the _sentence_lengths helper."""

    def test_empty_list(self) -> None:
        assert _sentence_lengths([]) == []

    def test_single_sentence(self) -> None:
        assert _sentence_lengths(["The cat sat."]) == [3]

    def test_multiple_sentences(self) -> None:
        sentences = ["Hello world.", "The quick brown fox jumps."]
        assert _sentence_lengths(sentences) == [2, 5]


class TestBurstiness:
    """Tests for _compute_burstiness. Implements P-inv-09."""

    def test_empty_returns_zero(self) -> None:
        assert _compute_burstiness([]) == 0.0

    def test_uniform_lengths_returns_zero(self) -> None:
        """All sentences same length → std=0 → CV=0."""
        assert _compute_burstiness([5, 5, 5, 5]) == 0.0

    def test_non_negative(self) -> None:
        """P-inv-09: burstiness is always ≥ 0."""
        result = _compute_burstiness([3, 7, 2, 10, 1])
        assert result >= 0.0

    def test_varied_lengths_positive(self) -> None:
        """Varied sentence lengths produce positive burstiness."""
        result = _compute_burstiness([2, 10, 3, 15])
        assert result > 0.0

    def test_single_sentence(self) -> None:
        """Single sentence → std=0 → CV=0."""
        assert _compute_burstiness([5]) == 0.0

    def test_zero_lengths(self) -> None:
        """All zero-length sentences → mean=0 → returns 0."""
        assert _compute_burstiness([0, 0, 0]) == 0.0


class TestLengthSkewness:
    """Tests for _compute_length_skewness."""

    def test_fewer_than_three_returns_zero(self) -> None:
        assert _compute_length_skewness([]) == 0.0
        assert _compute_length_skewness([5]) == 0.0
        assert _compute_length_skewness([5, 10]) == 0.0

    def test_symmetric_returns_near_zero(self) -> None:
        """Symmetric distribution has skewness ≈ 0."""
        result = _compute_length_skewness([5, 5, 5, 5, 5])
        assert abs(result) < 0.01

    def test_right_skewed_positive(self) -> None:
        """Right-skewed distribution has positive skewness."""
        result = _compute_length_skewness([1, 1, 1, 1, 1, 100])
        assert result > 0.0

    def test_returns_float(self) -> None:
        result = _compute_length_skewness([3, 5, 7, 9, 11])
        assert isinstance(result, float)


class TestHapaxRatio:
    """Tests for _compute_hapax_ratio."""

    def test_empty_returns_zero(self) -> None:
        assert _compute_hapax_ratio([]) == 0.0

    def test_all_unique_words(self) -> None:
        """When every word appears once, ratio = 1.0."""
        sentences = ["alpha beta gamma delta"]
        assert _compute_hapax_ratio(sentences) == 1.0

    def test_no_hapax(self) -> None:
        """When every word appears more than once, ratio = 0.0."""
        sentences = ["the the the", "the the"]
        assert _compute_hapax_ratio(sentences) == 0.0

    def test_mixed(self) -> None:
        """Mix of hapax and repeated words."""
        # "the" appears 3x, "cat" 1x, "sat" 1x → unique=3, hapax=2
        sentences = ["the cat sat", "the the"]
        result = _compute_hapax_ratio(sentences)
        assert abs(result - 2.0 / 3.0) < 1e-9

    def test_case_insensitive(self) -> None:
        """Words are lowercased before counting."""
        sentences = ["The the"]
        # "the" appears 2x → hapax=0, unique=1 → ratio=0.0
        assert _compute_hapax_ratio(sentences) == 0.0


class TestZipfRSquared:
    """Tests for _compute_zipf_r_squared."""

    def test_empty_returns_zero(self) -> None:
        assert _compute_zipf_r_squared([]) == 0.0

    def test_single_word_returns_one(self) -> None:
        assert _compute_zipf_r_squared(["hello"]) == 1.0

    def test_result_between_zero_and_one(self) -> None:
        """R² should be in [0, 1] for typical text."""
        sentences = [
            "The cat sat on the mat.",
            "The dog ran in the park.",
            "A bird flew over the tree.",
        ]
        result = _compute_zipf_r_squared(sentences)
        assert 0.0 <= result <= 1.0

    def test_returns_float(self) -> None:
        sentences = ["hello world hello"]
        result = _compute_zipf_r_squared(sentences)
        assert isinstance(result, float)

    def test_all_same_frequency(self) -> None:
        """All words same frequency → flat line → R²=1.0 (ss_tot=0)."""
        sentences = ["alpha beta gamma delta"]
        result = _compute_zipf_r_squared(sentences)
        assert result == 1.0


class TestPunctuationEntropy:
    """Tests for _compute_punctuation_entropy."""

    def test_no_punctuation_returns_zero(self) -> None:
        assert _compute_punctuation_entropy(["hello world"]) == 0.0

    def test_single_punctuation_type_returns_zero(self) -> None:
        """Only one type of punctuation → entropy = 0."""
        result = _compute_punctuation_entropy(["hello. world. test."])
        assert result == 0.0

    def test_two_equal_punctuation_types(self) -> None:
        """Two equally distributed types → entropy = 1.0 bit."""
        # 2 periods, 2 commas
        result = _compute_punctuation_entropy(["a, b. c, d."])
        assert abs(result - 1.0) < 0.01

    def test_entropy_non_negative(self) -> None:
        sentences = ["Hello! How are you? Fine, thanks."]
        result = _compute_punctuation_entropy(sentences)
        assert result >= 0.0

    def test_empty_returns_zero(self) -> None:
        assert _compute_punctuation_entropy([]) == 0.0


class TestStarterDiversity:
    """Tests for _compute_starter_diversity."""

    def test_empty_returns_zero(self) -> None:
        assert _compute_starter_diversity([], doc=None) == 0.0

    def test_all_same_starter(self) -> None:
        """All sentences start with the same word → diversity = 1/n."""
        sentences = ["The cat.", "The dog.", "The bird."]
        result = _compute_starter_diversity(sentences, doc=None)
        assert abs(result - 1.0 / 3.0) < 1e-9

    def test_all_unique_starters(self) -> None:
        """All sentences start with different words → diversity = 1.0."""
        sentences = ["Alpha one.", "Beta two.", "Gamma three."]
        result = _compute_starter_diversity(sentences, doc=None)
        assert result == 1.0

    def test_single_sentence(self) -> None:
        sentences = ["Hello world."]
        result = _compute_starter_diversity(sentences, doc=None)
        assert result == 1.0

    def test_case_insensitive(self) -> None:
        """Starters are lowercased."""
        sentences = ["The cat.", "the dog."]
        result = _compute_starter_diversity(sentences, doc=None)
        assert abs(result - 0.5) < 1e-9


class TestAnalyzeNaturalness:
    """Tests for the main analyze_naturalness function."""

    def test_returns_naturalness_result(self) -> None:
        sentences = [
            "The cat sat on the mat.",
            "It was a warm and sunny day.",
        ]
        result = analyze_naturalness(sentences, doc=None)
        assert isinstance(result, NaturalnessResult)

    def test_all_fields_are_floats(self) -> None:
        sentences = [
            "The cat sat on the mat.",
            "It was a warm and sunny day.",
            "Dogs are friendly animals.",
        ]
        result = analyze_naturalness(sentences, doc=None)
        assert isinstance(result.burstiness, float)
        assert isinstance(result.length_skewness, float)
        assert isinstance(result.hapax_ratio, float)
        assert isinstance(result.zipf_r_squared, float)
        assert isinstance(result.punctuation_entropy, float)
        assert isinstance(result.starter_diversity, float)

    def test_burstiness_non_negative(self) -> None:
        """P-inv-09: burstiness ≥ 0."""
        sentences = ["Short.", "A much longer sentence with many words."]
        result = analyze_naturalness(sentences, doc=None)
        assert result.burstiness >= 0.0

    def test_hapax_ratio_in_range(self) -> None:
        sentences = ["The cat sat on the mat."]
        result = analyze_naturalness(sentences, doc=None)
        assert 0.0 <= result.hapax_ratio <= 1.0

    def test_starter_diversity_in_range(self) -> None:
        sentences = ["The cat.", "A dog.", "The bird."]
        result = analyze_naturalness(sentences, doc=None)
        assert 0.0 <= result.starter_diversity <= 1.0

    def test_punctuation_entropy_non_negative(self) -> None:
        sentences = ["Hello! How are you? Fine, thanks."]
        result = analyze_naturalness(sentences, doc=None)
        assert result.punctuation_entropy >= 0.0

    def test_empty_sentences(self) -> None:
        """Edge case: empty sentence list."""
        result = analyze_naturalness([], doc=None)
        assert result.burstiness == 0.0
        assert result.length_skewness == 0.0
        assert result.hapax_ratio == 0.0
        assert result.zipf_r_squared == 0.0
        assert result.punctuation_entropy == 0.0
        assert result.starter_diversity == 0.0

    def test_single_sentence(self) -> None:
        result = analyze_naturalness(["Hello world."], doc=None)
        assert isinstance(result, NaturalnessResult)
        assert result.burstiness == 0.0  # single sentence → std=0
        assert result.length_skewness == 0.0  # <3 sentences

    def test_uniform_sentences_low_burstiness(self) -> None:
        """P-meta-03: uniform lengths → lower burstiness."""
        uniform = ["One two three.", "One two three.", "One two three."]
        varied = ["Hi.", "One two three four five six seven.", "Ok."]
        r_uniform = analyze_naturalness(uniform, doc=None)
        r_varied = analyze_naturalness(varied, doc=None)
        assert r_uniform.burstiness < r_varied.burstiness
