# Admin Page

The admin page allows users with the `is_admin` flag to manage quiz destinations through a browser-based interface.

## Navigation Flow

```mermaid
flowchart TD
    Login[Login Screen] --> Main[Main Screen]
    Main -->|"Admin Panel button<br>(admin users only)"| Admin[Admin Screen]
    Admin -->|"← Back to Main"| Main

    Admin --> List[Destinations List]
    Admin --> Form[Destination Form]
    Admin --> Dialog[Delete Confirmation]

    List -->|"Edit"| Form
    List -->|"Delete"| Dialog
    List -->|"Add New Destination"| Form

    Form -->|"Save"| API_Write[POST/PUT /api/admin/destinations]
    Form -->|"Cancel"| List
    Dialog -->|"Confirm"| API_Delete[DELETE /api/admin/destinations/:id]
    Dialog -->|"Cancel"| List

    API_Write -->|"Success"| List
    API_Delete -->|"Success"| List
```

## API Endpoints

```mermaid
flowchart LR
    subgraph Auth["Auth Layer"]
        direction TB
        A1[login_required] --> A2[admin_required]
        A2 --> A3[csrf_protected]
    end

    subgraph Endpoints["Admin API"]
        GET_LIST["GET /api/admin/destinations"]
        GET_ONE["GET /api/admin/destinations/:id"]
        POST["POST /api/admin/destinations"]
        PUT["PUT /api/admin/destinations/:id"]
        DELETE["DELETE /api/admin/destinations/:id"]
    end

    GET_LIST -.->|"auth only"| A2
    GET_ONE -.->|"auth only"| A2
    POST -.->|"auth + CSRF"| A3
    PUT -.->|"auth + CSRF"| A3
    DELETE -.->|"auth + CSRF"| A3
```

| Method | Endpoint | Auth | CSRF | Description |
|--------|----------|------|------|-------------|
| GET | `/api/admin/destinations` | admin | No | List all destinations (id + name) |
| GET | `/api/admin/destinations/:id` | admin | No | Get full destination data |
| POST | `/api/admin/destinations` | admin | Yes | Create a new destination |
| PUT | `/api/admin/destinations/:id` | admin | Yes | Replace all fields of a destination |
| DELETE | `/api/admin/destinations/:id` | admin | Yes | Delete destination + cascade results |

## Screen Layout

```
┌─────────────────────────────────────────────────────┐
│  🔧 Admin: Quiz Management          [← Back to Main]│
├─────────────────────────────────────────────────────┤
│  Total destinations: 3                               │
│  [Add New Destination]                               │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ #1  Paris                        [Edit] [Delete]│ │
│  ├─────────────────────────────────────────────────┤ │
│  │ #2  Tokyo                        [Edit] [Delete]│ │
│  ├─────────────────────────────────────────────────┤ │
│  │ #3  New York                     [Edit] [Delete]│ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Destination Form

```
┌─────────────────────────────────────────────────────┐
│  Add New Destination / Edit Destination              │
├─────────────────────────────────────────────────────┤
│  Name:      [________________________]               │
│                                                      │
│  Hint 1:    [________________________]               │
│  Hint 2:    [________________________]               │
│  Hint 3:    [________________________]               │
│  Hint 4:    [________________________]               │
│  Hint 5:    [________________________]               │
│                                                      │
│  Image URLs (2–10):                                  │
│    [https://example.com/img1.jpg        ] [✕]        │
│    [https://example.com/img2.jpg        ] [✕]        │
│    [+ Add Image URL]                                 │
│                                                      │
│  Correct Answers (1–20):                             │
│    [paris                               ] [✕]        │
│    [paris, france                       ] [✕]        │
│    [+ Add Answer]                                    │
│                                                      │
│  [Save]  [Cancel]                                    │
└─────────────────────────────────────────────────────┘
```

## Validation Rules

| Field | Constraints |
|-------|-------------|
| Name | 1–128 characters, not blank |
| Hints | Exactly 5, each 1–256 characters, not blank |
| Images | 2–10 URLs, each must start with `http://` or `https://` |
| Correct Answers | 1–20 items, each 1–128 characters |

Answers are normalized (lowercased + trimmed) before storage.

## Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Not authenticated |
| 403 | Not admin, or missing/invalid CSRF token |
| 400 | Validation failure (details in response) |
| 404 | Destination not found |
| 409 | Duplicate destination name |
