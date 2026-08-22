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

### 4. Install Apps Script sync

1. Open your spreadsheet → **Extensions → Apps Script**
2. Paste [apps-script/Code.gs](apps-script/Code.gs)
3. Save and run `setupTriggers` once (authorize when prompted)

### 5. Log a workout

Open any muscle tab (e.g. **Chest**), enter Date, Exercise (dropdown), Weight, and Notes.
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

## Project structure

```text
src/liftlogic/
  models.py         # WorkoutEntry, WorkoutInput, PersonalRecord
  parsing.py        # Canonical date/weight parsers
  validation.py     # Authoritative field validation rules
  reconcile.py      # Muscle tab vs Workout_Log drift detection
  repository.py     # get/add/update/delete/upsert workout data
  analytics.py      # PR and summary calculations
  exercises.py      # Seed exercise catalog and lookups
  setup.py          # setupSpreadsheet() — creates and configures the workbook
  sheets/client.py  # Google Sheets API wrapper and OAuth
  cli.py            # liftlogic CLI (setup / validate / reconcile)
apps-script/
  Code.gs           # Muscle tab → Workout_Log sync on edit
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
