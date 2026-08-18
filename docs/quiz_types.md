# Adding a Quiz Type

Quiz-type-independent gameplay is dispatched through adapters in
`backend/quiz_adapters.py`. Once a type is registered, the existing random,
GUID, active-quiz, hint, answer, sharing, statistics, guest migration, and
media-authorization flows use its adapter without route or frontend changes.

## Standard Types

`StandardQuizAdapter` supports the existing five-hint game format. A standard
question model must provide:

- An integer `id` primary key
- `name`
- `hint1` through `hint5`
- `correct_answers` as a JSON list of normalized answers

Provide separate authenticated and guest result models. Both use the existing
attempt fields `hint_difficulty`, `remaining_guesses`, and `ongoing`. The user
model uses a `user_id` key, and the guest model uses `guest_session_id`. Their
quiz source key may have any name and is supplied as `result_source_field`.

Register the adapter:

```python
register_quiz_adapter(
    StandardQuizAdapter(
        identifier="cities",
        question_model=City,
        user_result_model=CityQuizResult,
        guest_result_model=GuestCityQuizResult,
        result_source_field="city_id",
    )
)
```

Add the matching `QuizType` entry in `backend/quiz_types.py` and add its rules
file under `backend/assets/rules/`:

```python
QuizType(
    identifier="cities",
    display_name="Cities",
    rules_file="cities.md",
    source_table="cities",
    adapter="cities",
)
```

The type identifier, adapter identifier, media namespace, and public API value
must agree. Startup validation fails when a registry entry has no adapter or
uses a mismatched adapter.

Place media under `media/<type>/<source-id>/` using the same hint filename
convention as countries. The frontend sends the selected identifier to
`GET /api/quiz?type=<identifier>`.

## Data Management
## Data Management

The central GUID catalog automatically backfills every registered source table
that has an `id` column. Standard types also receive shared data management:

- The seed command loads `data/<identifier>.json` and skips populated types
    independently. Automation may pass records through the `quiz_data` mapping.
- The admin screen lists all registered types and reuses the standard question
    form for create, update, and delete operations.
- Generic admin endpoints are available under
    `/api/admin/quiz-types/<identifier>/questions`.

Custom adapters with a different data shape should provide their own import
and admin interface because the standard validation contract does not apply.

## Custom Gameplay

Types with a different hint structure, scoring model, or media layout should
implement the `QuizAdapter` protocol instead of using `StandardQuizAdapter`.
Shared routes remain unchanged as long as the adapter fulfills the question,
result, and media operations in that protocol.