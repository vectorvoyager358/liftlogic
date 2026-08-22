"""Sheet names, column headers, and shared constants."""

SPREADSHEET_TITLE = "LiftLogic"

# Visible tabs
DASHBOARD_SHEET = "Dashboard"
MUSCLE_TABS = [
    "Chest",
    "Back",
    "Shoulders",
    "Biceps",
    "Triceps",
    "Legs",
    "Cardio",
]

# Hidden/internal tabs
WORKOUT_LOG_SHEET = "Workout_Log"
EXERCISES_SHEET = "Exercises"
SETTINGS_SHEET = "Settings"
ANALYTICS_SHEET = "Analytics"
AI_INSIGHTS_SHEET = "AI_Insights"

HIDDEN_SHEETS = [
    WORKOUT_LOG_SHEET,
    EXERCISES_SHEET,
    SETTINGS_SHEET,
    AI_INSIGHTS_SHEET,
]

ALL_SHEETS = [DASHBOARD_SHEET, *MUSCLE_TABS, *HIDDEN_SHEETS]

WORKOUT_ENTRY_COLUMNS = ["Date", "Exercise", "Weight", "Notes"]

WORKOUT_LOG_COLUMNS = [
    "Log ID",
    "Date",
    "Muscle",
    "Exercise ID",
    "Exercise",
    "Weight",
    "Notes",
    "Source Row",
]

EXERCISE_COLUMNS = [
    "Exercise ID",
    "Exercise",
    "Primary Muscle",
    "Secondary Muscle",
    "Equipment",
]

SETTINGS_ROWS = [
    ("weight_unit", "lb"),
    ("spreadsheet_version", "0.1.0"),
]

# Dashboard cell that liftlogic refresh writes the last-refreshed timestamp to
DASHBOARD_LAST_REFRESHED_CELL = "Dashboard!A2"

# Analytics tab section headers and table headers (used for conditional formatting)
ANALYTICS_SECTION_NAMES = [
    "OVERALL STATISTICS",
    "PERSONAL RECORDS",
    "MUSCLE FREQUENCY",
    "EXERCISE TRENDS",
]
ANALYTICS_TABLE_HEADERS = ["Metric", "Exercise", "Muscle"]

HEADER_ROW = 1
DATA_START_ROW = 2

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

CREDENTIALS_DIR = "credentials"
TOKEN_FILE = "credentials/token.json"
CLIENT_SECRETS_FILE = "credentials/client_secret.json"
