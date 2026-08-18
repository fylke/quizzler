```mermaid
erDiagram
    countries {
        number id PK
        varchar2 name
        varchar2 hint1
        varchar2 hint2
        varchar2 hint3
        varchar2 hint4
        varchar2 hint5
        json correct_answers
    }

    quiz_identity {
        varchar2 guid PK
        varchar2 quiz_type
        number source_id
    }

    user {
        number id PK
        varchar2 password_hash
        varchar2 name
        varchar2 email
        boolean is_admin
    }

    quiz_result {
        number user_id FK
        number destination_id FK
        number hint_difficulty
        number remaining_guesses
        boolean ongoing
    }

    user ||--o{ quiz_result : "has"
    countries ||--o{ quiz_result : "referenced by"
    quiz_identity }o--|| countries : "countries source_id"
```

`quiz_identity` is a polymorphic public-identity catalog. Its
`(quiz_type, source_id)` pair is unique, while `guid` is a canonical UUID v4
used by public quiz lookup and links such as `/?quiz=<guid>`. The catalog does
not use a database foreign key because registered quiz types may use different
source tables.

GUIDs are generated per deployment. Restoring the database preserves them;
rebuilding a database from source data may produce different GUIDs. Integer
source IDs remain internal keys for result relationships, scoring, complaints,
and media directories.
