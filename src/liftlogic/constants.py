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

GOALS_SHEET = "Goals"

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

ALL_SHEETS = [DASHBOARD_SHEET, *MUSCLE_TABS, GOALS_SHEET, *HIDDEN_SHEETS]

WORKOUT_ENTRY_COLUMNS = ["Date", "Exercise", "Weight", "Notes"]

GOAL_COLUMNS = [
    "Goal ID",
    "Type",
    "Exercise",
    "Muscle",
    "Target",
    "Unit",
    "Target Date",
    "Status",
    "Notes",
]

GOAL_TYPES = ["Exercise", "Muscle"]
GOAL_STATUS_OPTIONS = ["Active", "Completed", "Paused"]
GOAL_UNITS = ["lb", "sessions/week"]

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

# Dashboard — interactive tracker (populated by Apps Script refreshDashboard)
DASHBOARD_CTRL_MUSCLE_CELL = "Dashboard!B3"
DASHBOARD_CTRL_VIEW_CELL = "Dashboard!D3"
DASHBOARD_CTRL_SEARCH_CELL = "Dashboard!F3"
DASHBOARD_CTRL_EXERCISE_CELL = "Dashboard!I3"
DASHBOARD_KPI_EXERCISES_CELL = "Dashboard!B6"
DASHBOARD_KPI_ENTRIES_CELL = "Dashboard!E6"
DASHBOARD_KPI_TOPLIFT_CELL = "Dashboard!H6"
DASHBOARD_KPI_TOPLIFT_EXERCISE_CELL = "Dashboard!J6"
DASHBOARD_SECTION_TITLE_CELL = "Dashboard!A7"
DASHBOARD_HEADER_ROW = 8
DASHBOARD_DATA_START_ROW = 9
DASHBOARD_VIEW_OPTIONS = ["Summary", "Workout Log"]
DASHBOARD_MUSCLE_FILTER_OPTIONS = ["All", *MUSCLE_TABS]
DASHBOARD_SEARCH_HINT = "Type an exercise name or notes to filter"

# Dashboard subtitle (also updated by Apps Script on refresh)
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
