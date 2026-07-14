# Quiz Images (media/)

Quiz images are stored locally in the `media/` directory (gitignored). The app serves them via `/media/<path>`.

## Naming Convention

```
media/<table>/<id>/<hint_level>a.jpg
media/<table>/<id>/<hint_level>b.jpg
media/<table>/<id>/<hint_level>a_small.webp
media/<table>/<id>/<hint_level>b_small.webp
```

Each entry has two images per hint level. For example, country with ID 3 at hint level 5:

```
media/countries/3/5a.jpg
media/countries/3/5b.jpg
```

Optimized variants (preferred by the API when present):

```
media/countries/3/5a_small.webp
media/countries/3/5b_small.webp
```

The API returns these paths automatically based on the quiz type, destination ID, and current hint difficulty.

## Access Control

- Hint images are served from `/media/<path>` only when the requester is the active player for the destination.
- Unlocked image levels are the current live hint and previously revealed harder hints (`requested_level >= current_hint_difficulty`).
- To reduce latency while loading new hints, the server first checks a signed-session media access cache (`destination_id`, `hint_difficulty`) before falling back to a database active-quiz lookup.
- For each hint slot (`a`, `b`), the quiz API prefers `_small.webp` and falls back to `.jpg` if optimized files are missing.

## Generate Optimized Hint Images

Generate `_small.webp` files for existing hint images:

```bash
just generate-small-webp
```

Direct command with custom settings:

```bash
uv run generate-small-webp --root media/countries --max-width 960 --max-height 960 --quality 72
```

Optional overwrite of existing optimized files:

```bash
just generate-small-webp overwrite=true
```

### Result Screen Images

When a quiz is finished (correct answer or out of guesses), the API can also return up to 10 additional images for the results screen.

- Store these files in the same destination directory.
- File names must start with `0` (for example: `01.jpg`, `02.jpg`, `0a.png`).
- Supported extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`.
- Files are returned in filename order, max 10 items.

## Setup

1. Create the `media/` directory at the project root
2. Inside `media/`, create a subdirectory per quiz type (e.g. `countries/`)
3. Inside each quiz-type directory, create subdirectories named by database ID
4. Place images using the naming convention above

## Container Deployment

The `media/` directory is bind-mounted read-only into the container:

```yaml
volumes:
  - ./media:/app/media:ro
```
