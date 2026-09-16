```mermaid
erDiagram
    countries {
        number id PK
        varchar2 name
        varchar2 hint1
        varchar2 hint1_source
        varchar2 hint2
        varchar2 hint2_source
        varchar2 hint3
        varchar2 hint3_source
        varchar2 hint4
        varchar2 hint4_source
        varchar2 hint5
        varchar2 hint5_source
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
        varchar2 email
        boolean is_admin
    }

    hint_source_review {
        number id PK
        varchar2 quiz_type
        number source_id
        number hint_difficulty
        boolean reviewed
        datetime reviewed_at
        number reviewed_by_user_id FK
    }

    quiz_result {
        number user_id FK
        number destination_id FK
        number hint_difficulty
        number remaining_guesses
        boolean ongoing
    }

    app_settings {
        varchar2 key PK
        varchar2 value
    }

    user ||--o{ quiz_result : "has"
    countries ||--o{ quiz_result : "referenced by"
    quiz_identity }o--|| countries : "countries source_id"
    user ||--o{ hint_source_review : "reviews"
```

`quiz_identity` is a polymorphic public-identity catalog. Its
`(quiz_type, source_id)` pair is unique. The `guid` column is an internal
canonical UUID v4 key; public lookup and links use a compact type-scoped ID such
as `c42` in `/quiz/c42`. The catalog does not use a database foreign key because
registered quiz types may use different source tables.

Restoring the database preserves the internal identity rows and their existing
links. Rebuilding a database from source data preserves the compact IDs as long
as the source IDs and registered type codes remain unchanged. Integer source IDs
remain the keys for result relationships, scoring, complaints, and media
directories.

`app_settings` stores key-value configuration for application-level settings,
such as `background_portrait` and `background_landscape` media paths.

`hint_source_review` stores review workflow state independently from quiz
content. Its `(quiz_type, source_id, hint_difficulty)` tuple is unique so each
populated hint source can be reviewed independently across registered quiz
types. A missing or false review row means the source is unreviewed. Reviewed
rows retain the administrator and UTC timestamp. Updating a source through the
admin API removes its prior review state so changed content returns to the
queue; deleting a question removes its review rows.
