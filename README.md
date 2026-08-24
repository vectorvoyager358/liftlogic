# LiftLogic

An AI-powered workout tracking, analytics, and coaching system built around Google Sheets.

## Backend-first development

LiftLogic prioritizes **data model integrity, validation, and repository APIs** over UI polish. Google Sheets is the current UI; `Workout_Log` is canonical. All writes go through validated repository methods. The UI can be redesigned freely once the backend is solid.

```text
Muscle tabs (entry UI)
        │
        ▼ Apps Script sync
   Workout_Log (canonical data store)
        │
        ▼ Python repository
   Analytics / Validation / Reconciliation
```

## Quick start

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Google Cloud setup

1. Create a Google Cloud project
2. Enable **Google Sheets API** and **Google Drive API**
3. Create OAuth 2.0 Desktop credentials
4. Save the downloaded JSON as `credentials/client_secret.json`

See [credentials/README.md](credentials/README.md) for details.

### 3. Bootstrap the spreadsheet

```bash
liftlogic setup --write-config
```

### 4. Install Apps Script (sync + Dashboard + HTML tracker)

1. Open your spreadsheet → **Extensions → Apps Script**
2. Replace `Code.gs` with [apps-script/Code.gs](apps-script/Code.gs)
3. Add an HTML file named **`Sidebar`** (File → New → HTML) and paste [apps-script/Sidebar.html](apps-script/Sidebar.html)
4. Save and run `setupTriggers` once (authorize when prompted)
5. Reload the spreadsheet → **LiftLogic → Open Workout Tracker**

The sidebar provides the premium tracker UI: muscle filter, Summary/Log toggle, search, exercise filter, KPI cards, and a styled data table. Filter changes sync back to the Dashboard sheet automatically.

**Dashboard sheet controls** (row 3) mirror the sidebar filters:

| Control | Cell | Purpose |
| ------- | ---- | ------- |
| MUSCLE | B3 | Filter by muscle group or All |
| VIEW | D3 | **Summary** (best per exercise) or **Workout Log** (all entries) |
| SEARCH | F3 | Filter by exercise name or notes (hover the cell for a hint; leave blank for no filter) |
| EXERCISE | I3 | Filter to one exercise |

Use **LiftLogic → Refresh Dashboard** after bulk edits, or change any filter to refresh automatically.

### 5. Log a workout

Open any muscle tab (e.g. **Chest**), enter Date, Exercise (dropdown), Weight/metric, and Notes.

**Exercise catalog sync**

| Action | Result |
|--------|--------|
| Add exercise on muscle tab / sidebar **Other…** | Added to **Exercises** + dropdowns |
| Rename on **Exercises** sheet (name column) | Updates that name on muscle tabs, Workout_Log, Goals + dropdowns. Refresh the sidebar to see it. |
| Delete / clear a **custom** exercise on a muscle tab (last use) | Removed from **Exercises** + dropdowns (built-in seed exercises are kept) |
| Delete row on **Exercises** sheet | Removed from muscle-tab + sidebar dropdowns (after refresh). Old workout logs are kept. |
| Delete a workout row on a muscle tab | Only that log entry is removed — exercise stays in **Exercises** |
| Re-import typed names | **LiftLogic → Import Exercises from Muscle Tabs** |

Sidebar: click **Refresh** (or reopen it) after changing the Exercises sheet so its dropdown reloads.
The row is synced to `Workout_Log` automatically via Apps Script.

### 6. Data quality checks

```bash
liftlogic validate      # scan Workout_Log for field errors and warnings
liftlogic reconcile     # compare muscle tabs vs Workout_Log for drift
```

## CLI reference

| Command | Description |
| ------- | ----------- |
| `liftlogic setup` | Create and configure a new LiftLogic spreadsheet |
| `liftlogic setup --write-config` | Also save the spreadsheet ID to `credentials/spreadsheet.json` |
| `liftlogic validate` | Validate every row in Workout_Log |
| `liftlogic reconcile` | Detect drift between muscle tabs and Workout_Log |
| `liftlogic stats` | Print workout stats to the terminal |
| `liftlogic refresh` | Write computed analytics to the Analytics tab |
| `liftlogic format` | Apply visual formatting to Dashboard, muscle tabs, and Analytics |
| `liftlogic ask "…"` | Ask a natural-language question (requires NVIDIA NIM) |
| `liftlogic insights` | Generate AI coaching summary and write to AI_Insights tab |
| `liftlogic search-notes "…"` | Search workout notes by keyword (RAG preview) |
| `liftlogic goals` | Show progress toward active goals |

Install AI dependencies: `pip install -e ".[ai]"`. Configure `credentials/nim.json` — see [credentials/README.md](credentials/README.md).

## Project structure

```text
src/liftlogic/
  models.py         # WorkoutEntry, WorkoutInput, PersonalRecord
  parsing.py        # Canonical date/weight parsers
  validation.py     # Authoritative field validation rules
  reconcile.py      # Muscle tab vs Workout_Log drift detection
  repository.py     # get/add/update/delete/upsert workout data
  analytics.py      # PR, streaks, trends, plateau detection
  dashboard.py      # Analytics tab refresh and terminal stats
  ai.py             # NVIDIA NIM coach (ask / insights)
  exercises.py      # Seed exercise catalog and lookups
  setup.py          # setupSpreadsheet() — creates and configures the workbook
  sheets/client.py  # Google Sheets API wrapper and OAuth
  cli.py            # liftlogic CLI
apps-script/
  Code.gs           # Muscle tab sync + Dashboard refresh + sidebar API
  Sidebar.html      # Premium HTML workout tracker sidebar
tests/
  test_parsing.py
  test_validation.py
  test_reconcile.py
  test_repository.py
  test_analytics.py
```

## Development

```bash
pytest
ruff check src tests
```

## License

See [LICENSE](LICENSE).
