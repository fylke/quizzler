"""Unit tests for backend.admin validation and normalization functions."""

from backend.admin import normalize_answers, validate_destination_payload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_payload(**overrides) -> dict:
    """Return a minimal valid destination payload, with optional overrides."""
    payload = {
        "name": "Paris",
        "hints": [
            "Hint one",
            "Hint two",
            "Hint three",
            "Hint four",
            "Hint five",
        ],
        "correct_answers": ["paris", "paris, france"],
    }
    payload.update(overrides)
    return payload


# ===========================================================================
# validate_destination_payload – happy path
# ===========================================================================


class TestValidateDestinationPayloadValid:
    def test_valid_payload_passes(self):
        is_valid, errors = validate_destination_payload(_valid_payload())
        assert is_valid is True
        assert errors == []


# ===========================================================================
# validate_destination_payload – name field
# ===========================================================================


class TestValidateNameField:
    def test_missing_name_returns_error(self):
        payload = _valid_payload()
        del payload["name"]
        is_valid, errors = validate_destination_payload(payload)
        assert is_valid is False
        assert any("name" in e for e in errors)

    def test_blank_name_returns_error(self):
        is_valid, errors = validate_destination_payload(_valid_payload(name=""))
        assert is_valid is False
        assert any("name" in e and "blank" in e for e in errors)

    def test_whitespace_only_name_returns_error(self):
        is_valid, errors = validate_destination_payload(_valid_payload(name="   "))
        assert is_valid is False
        assert any("name" in e and "blank" in e for e in errors)

    def test_name_exceeding_128_chars_returns_error(self):
        long_name = "a" * 129
        is_valid, errors = validate_destination_payload(_valid_payload(name=long_name))
        assert is_valid is False
        assert any("name" in e for e in errors)

    def test_name_exactly_128_chars_is_valid(self):
        name_128 = "a" * 128
        is_valid, errors = validate_destination_payload(_valid_payload(name=name_128))
        assert is_valid is True
        assert errors == []


# ===========================================================================
# validate_destination_payload – hints field
# ===========================================================================


class TestValidateHintsField:
    def test_missing_hints_returns_error(self):
        payload = _valid_payload()
        del payload["hints"]
        is_valid, errors = validate_destination_payload(payload)
        assert is_valid is False
        assert any("hints" in e for e in errors)

    def test_fewer_than_5_hints_returns_error(self):
        is_valid, errors = validate_destination_payload(
            _valid_payload(hints=["h1", "h2", "h3", "h4"])
        )
        assert is_valid is False
        assert any("hints" in e and "5" in e for e in errors)

    def test_more_than_5_hints_returns_error(self):
        is_valid, errors = validate_destination_payload(_valid_payload(hints=["h"] * 6))
        assert is_valid is False
        assert any("hints" in e and "5" in e for e in errors)

    def test_blank_hint_returns_error(self):
        hints = ["valid"] * 4 + [""]
        is_valid, errors = validate_destination_payload(_valid_payload(hints=hints))
        assert is_valid is False
        assert any("hints" in e and "blank" in e for e in errors)

    def test_hint_exceeding_256_chars_returns_error(self):
        hints = ["valid"] * 4 + ["x" * 257]
        is_valid, errors = validate_destination_payload(_valid_payload(hints=hints))
        assert is_valid is False
        assert any("hints" in e for e in errors)

    def test_hint_exactly_256_chars_is_valid(self):
        hints = ["valid"] * 4 + ["x" * 256]
        is_valid, errors = validate_destination_payload(_valid_payload(hints=hints))
        assert is_valid is True
        assert errors == []


# ===========================================================================
# validate_destination_payload – images field
# ===========================================================================


# ===========================================================================
# validate_destination_payload – correct_answers field
# ===========================================================================


class TestValidateCorrectAnswersField:
    def test_missing_correct_answers_returns_error(self):
        payload = _valid_payload()
        del payload["correct_answers"]
        is_valid, errors = validate_destination_payload(payload)
        assert is_valid is False
        assert any("correct_answers" in e for e in errors)

    def test_empty_correct_answers_returns_error(self):
        is_valid, errors = validate_destination_payload(
            _valid_payload(correct_answers=[])
        )
        assert is_valid is False
        assert any("correct_answers" in e for e in errors)

    def test_more_than_20_correct_answers_returns_error(self):
        answers = [f"answer{i}" for i in range(21)]
        is_valid, errors = validate_destination_payload(
            _valid_payload(correct_answers=answers)
        )
        assert is_valid is False
        assert any("correct_answers" in e for e in errors)

    def test_answer_exceeding_128_chars_returns_error(self):
        answers = ["a" * 129]
        is_valid, errors = validate_destination_payload(
            _valid_payload(correct_answers=answers)
        )
        assert is_valid is False
        assert any("correct_answers" in e for e in errors)

    def test_exactly_1_answer_is_valid(self):
        is_valid, errors = validate_destination_payload(
            _valid_payload(correct_answers=["paris"])
        )
        assert is_valid is True
        assert errors == []

    def test_exactly_20_answers_is_valid(self):
        answers = [f"answer{i}" for i in range(20)]
        is_valid, errors = validate_destination_payload(
            _valid_payload(correct_answers=answers)
        )
        assert is_valid is True
        assert errors == []


# ===========================================================================
# validate_destination_payload – multiple errors
# ===========================================================================


class TestValidateMultipleErrors:
    def test_multiple_errors_reported_when_multiple_fields_invalid(self):
        payload = {
            "name": "",
            "hints": ["only one"],
            "images": ["bad-url"],
            "correct_answers": [],
        }
        is_valid, errors = validate_destination_payload(payload)
        assert is_valid is False
        # We expect at least one error per invalid field
        fields_with_errors = {e.split(":")[0].split("[")[0] for e in errors}
        assert "name" in fields_with_errors
        assert "hints" in fields_with_errors
        assert "images" in fields_with_errors
        assert "correct_answers" in fields_with_errors


# ===========================================================================
# normalize_answers
# ===========================================================================


class TestNormalizeAnswers:
    def test_mixed_case_strings_are_lowercased(self):
        assert normalize_answers(["PARIS", "Tokyo"]) == ["paris", "tokyo"]

    def test_leading_trailing_whitespace_is_stripped(self):
        assert normalize_answers(["  paris  ", "  tokyo  "]) == ["paris", "tokyo"]

    def test_already_normalized_strings_pass_through(self):
        assert normalize_answers(["paris", "tokyo"]) == ["paris", "tokyo"]

    def test_empty_list_returns_empty_list(self):
        assert normalize_answers([]) == []

    def test_combined_case_and_whitespace(self):
        result = normalize_answers(["  PARIS, France  "])
        assert result == ["paris, france"]
