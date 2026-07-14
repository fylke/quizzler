```mermaid
sequenceDiagram
    title Fetch next hint for a destination

    actor User
    participant Frontend
    participant Backend
    participant Database

    alt Start a new quiz
        User->>Frontend: Clicks "Run Random Quiz"
    else Next hint
        User->>Frontend: Clicks "Next Hint"
    end

    Frontend->>Backend: GET /api/hint (sessionId: "token")

    Backend->>Database: SELECT quiz_result WHERE user_id = :uid AND ongoing = true
    Database->>Backend: QuizResult(hint_difficulty, remaining_guesses, destination_id)

    alt no active quiz
        Backend->>Frontend: (404, {error: "No active quiz"})
        Frontend->>User: Display error message
    else hint_difficulty = 0
        Backend->>Frontend: (404, {error: "No more hints remaining"})
        Frontend->>User: Remain on quiz screen and display message<br/>"No more hints remaining, you might as well guess now!"
    else hint available
        Backend->>Database: SELECT countries WHERE id = :destination_id
        Database->>Backend: Country(hint1..hint5)
        Backend->>Database: UPDATE quiz_result SET hint_difficulty = hint_difficulty - 1
        Database->>Backend: OK
        Backend->>Backend: Store {destination_id, hint_difficulty} in signed session for media auth
        Backend->>Frontend: (200, {hint: "The city is known for its iconic opera house.",<br/>hintDifficulty: 2, remainingGuesses: 2,<br/>images: ["/media/countries/12/2a.jpg", "/media/countries/12/2b.jpg"]})
        Frontend->>User: Display hint and remaining guesses
    end
```

## Performance Note

- Hint image authorization now uses a session-cached media access state (`destination_id`, `hint_difficulty`) that is updated on quiz start, hint changes, and active-quiz restore.
- This avoids repeated active-quiz database lookups for each `/media/...` hint image request during normal hint navigation.
- If the session cache is absent, the server falls back to the database-backed authorization check.

## Hint Review Behavior

- The frontend stores unlocked hints per difficulty and renders review buttons in descending difficulty order.
- The active review selection is tracked separately from live server progression, so users can inspect earlier hints without changing backend state.
- Each unlocked hint difficulty keeps its own image pair.
- When a user clicks an older hint in review, both hint text and quiz images switch to that hint's snapshot.
- If a saved image pair is unavailable, the frontend falls back to deterministic URLs using destination id and difficulty (`/media/countries/<id>/<difficulty>a.jpg`, `/media/countries/<id>/<difficulty>b.jpg`).
