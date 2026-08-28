/**
 * LiftLogic — muscle-tab sync + interactive Dashboard.
 *
 * Install:
 *   1. Extensions → Apps Script
 *   2. Add Code.gs and Sidebar.html (see apps-script/ in the repo)
 *   3. Save → run setupTriggers (authorize when prompted)
 *   4. Reload the spreadsheet → LiftLogic menu → Open Workout Tracker
 *
 * To test from the editor, run refreshDashboard (not onOpen — getUi needs an open sheet).
 */

var MUSCLE_TABS = ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Cardio'];

var ENTRY_COLUMNS = {
  DATE: 0,
  EXERCISE: 1,
  WEIGHT: 2,
  NOTES: 3,
};

var LOG_COLUMNS = {
  LOG_ID: 0,
  DATE: 1,
  MUSCLE: 2,
  EXERCISE_ID: 3,
  EXERCISE: 4,
  WEIGHT: 5,
  NOTES: 6,
  SOURCE_ROW: 7,
};

// Dashboard layout — must match liftlogic setup.py / constants.py
var DASHBOARD_CFG = {
  MUSCLE: 'B3',
  VIEW: 'D3',
  SEARCH: 'F3',
  EXERCISE: 'I3',
  KPI_EXERCISES: 'B6',
  KPI_ENTRIES: 'E6',
  KPI_TOPLIFT: 'H6',
  KPI_TOPLIFT_EXERCISE: 'J6',
  SECTION_TITLE: 'A7',
  HEADER_ROW: 8,
  DATA_START_ROW: 9,
  DATA_COLS: 6,
  MAX_DATA_ROWS: 100,
  SEARCH_HINT: 'Type an exercise name or notes to filter',
};

var WORKOUT_LOG = 'Workout_Log';
var EXERCISES = 'Exercises';
var DASHBOARD = 'Dashboard';

var DASHBOARD_CONTROL_CELLS = ['B3', 'D3', 'F3', 'I3'];

// Cardio + bodyweight metrics — mirror liftlogic.exercises
var EXERCISE_CATALOG = [
  { name: 'Barbell Bench Press', muscle: 'Chest', metric: 'lb' },
  { name: 'Incline Dumbbell Press', muscle: 'Chest', metric: 'lb' },
  { name: 'Cable Fly', muscle: 'Chest', metric: 'lb' },
  { name: 'Push-Up', muscle: 'Chest', metric: 'reps' },
  { name: 'Lat Pulldown', muscle: 'Back', metric: 'lb' },
  { name: 'Barbell Row', muscle: 'Back', metric: 'lb' },
  { name: 'Pull-Up', muscle: 'Back', metric: 'reps' },
  { name: 'Seated Cable Row', muscle: 'Back', metric: 'lb' },
  { name: 'Overhead Press', muscle: 'Shoulders', metric: 'lb' },
  { name: 'Lateral Raise', muscle: 'Shoulders', metric: 'lb' },
  { name: 'Face Pull', muscle: 'Shoulders', metric: 'lb' },
  { name: 'Barbell Curl', muscle: 'Biceps', metric: 'lb' },
  { name: 'Hammer Curl', muscle: 'Biceps', metric: 'lb' },
  { name: 'Tricep Pushdown', muscle: 'Triceps', metric: 'lb' },
  { name: 'Skull Crusher', muscle: 'Triceps', metric: 'lb' },
  { name: 'Back Squat', muscle: 'Legs', metric: 'lb' },
  { name: 'Romanian Deadlift', muscle: 'Legs', metric: 'lb' },
  { name: 'Leg Press', muscle: 'Legs', metric: 'lb' },
  { name: 'Walking Lunge', muscle: 'Legs', metric: 'lb' },
  { name: 'Treadmill Run', muscle: 'Cardio', metric: 'minutes' },
  { name: 'Stationary Bike', muscle: 'Cardio', metric: 'minutes' },
  { name: 'Rowing Machine', muscle: 'Cardio', metric: 'minutes' },
  { name: 'Steps', muscle: 'Cardio', metric: 'steps' },
  { name: 'Jump Rope', muscle: 'Cardio', metric: 'minutes' },
  { name: 'Elliptical', muscle: 'Cardio', metric: 'minutes' },
];

var METRIC_LABELS = {
  lb: 'Weight (lb)',
  reps: 'Reps',
  steps: 'Steps',
  minutes: 'Minutes',
};

// ---------------------------------------------------------------------------
// Menu + triggers
// ---------------------------------------------------------------------------

function onOpen() {
  try {
    SpreadsheetApp.getUi()
      .createMenu('LiftLogic')
      .addItem('Open Workout Tracker', 'openTrackerSidebar')
      .addItem('Refresh Dashboard', 'refreshDashboard')
      .addItem('Sync All Muscle Tabs', 'syncAllMuscleTabs')
      .addItem('Refresh Exercise Dropdowns', 'refreshExerciseDropdowns')
      .addItem('Import Exercises from Muscle Tabs', 'importExercisesFromMuscleTabs')
      .addItem('Remove Unused Custom Exercises', 'pruneUnusedCustomExercises')
      .addItem("Insert Today's Date", 'insertTodaysDate')
      .addSeparator()
      .addItem('Setup Edit Triggers', 'setupTriggers')
      .addToUi();
  } catch (err) {
    // getUi() is unavailable when onOpen is run from the Apps Script editor.
    console.log('LiftLogic menu skipped (no spreadsheet UI): ' + err);
  }
  try {
    refreshDashboard();
  } catch (err) {
    console.error('refreshDashboard failed on open: ' + err);
  }
}

function insertTodaysDate() {
  var range = SpreadsheetApp.getActiveRange();
  if (!range) return;
  var sheet = range.getSheet();
  var name = sheet.getName();
  if (MUSCLE_TABS.indexOf(name) === -1 && name !== 'Goals') {
    SpreadsheetApp.getUi().alert(
      "Select a Date cell on a muscle tab (column A) or Goals Target Date, then try again."
    );
    return;
  }
  var today = new Date();
  today.setHours(12, 0, 0, 0);
  range.setValue(today);
  range.setNumberFormat('yyyy-mm-dd');
}

function logWorkoutEntry(payload) {
  payload = payload || {};
  var muscle = String(payload.muscle || '').trim();
  var exercise = String(payload.exercise || '').trim();
  var notes = String(payload.notes || '').trim();
  var weight = payload.weight;
  var dateStr = String(payload.date || '').trim();

  if (MUSCLE_TABS.indexOf(muscle) === -1) {
    throw new Error('Pick a muscle tab (not All).');
  }
  if (!exercise) {
    throw new Error('Exercise is required.');
  }
  if (!dateStr) {
    throw new Error('Date is required.');
  }

  var dateParts = dateStr.split('-');
  if (dateParts.length !== 3) {
    throw new Error('Date must be YYYY-MM-DD.');
  }
  var dateVal = new Date(
    Number(dateParts[0]),
    Number(dateParts[1]) - 1,
    Number(dateParts[2]),
    12, 0, 0
  );
  if (isNaN(dateVal.getTime())) {
    throw new Error('Invalid date.');
  }
  if (!isValidWeight_(weight, muscle, exercise)) {
    var metric = metricFor_(exercise, muscle);
    var label = METRIC_LABELS[metric] || 'Value';
    throw new Error(label + ' must be greater than 0.');
  }

  // New exercise names are added to the Exercises sheet so all dropdowns stay in sync
  ensureExerciseInCatalog_(exercise, muscle);

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(muscle);
  if (!sheet) {
    throw new Error('Missing sheet: ' + muscle);
  }

  sheet.appendRow([dateVal, exercise, Number(weight), notes]);
  var row = sheet.getLastRow();
  sheet.getRange(row, 1).setNumberFormat('yyyy-mm-dd');
  syncRow_(sheet, row, muscle);
  refreshMuscleExerciseDropdowns_();
  refreshDashboard();

  return getTrackerPayload_(
    normalizeTrackerFilters_({
      muscle: muscle,
      view: 'Workout Log',
      search: '',
      exercise: 'All',
    }),
    { syncSheet: false }
  );
}

function openTrackerSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('LiftLogic Tracker')
    .setWidth(440);
  SpreadsheetApp.getUi().showSidebar(html);
}

function getTrackerBootstrap() {
  var filters = readDashboardFilters_();
  return getTrackerPayload_(filters, { syncSheet: false });
}

function getTrackerData(filters) {
  return getTrackerPayload_(normalizeTrackerFilters_(filters), { syncSheet: false });
}

function applyTrackerFilters(filters) {
  var normalized = normalizeTrackerFilters_(filters);
  writeDashboardFilters_(normalized);
  refreshDashboard();
  return getTrackerPayload_(normalized, { syncSheet: false });
}

function syncAllAndRefresh() {
  syncAllMuscleTabs();
  return getTrackerPayload_(readDashboardFilters_(), { syncSheet: false });
}

function setupTriggers() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'onEditSync') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger('onEditSync')
    .forSpreadsheet(ss)
    .onEdit()
    .create();
}

function onEditSync(e) {
  if (!e || !e.range) return;

  var sheet = e.range.getSheet();
  var sheetName = sheet.getName();

  if (sheetName === DASHBOARD) {
    if (isDashboardControlEdit_(e.range.getA1Notation())) {
      refreshDashboard();
    }
    return;
  }

  // Exercises sheet edits → rename propagation + refresh dropdowns
  if (sheetName === EXERCISES) {
    if (e.range.getRow() === 1) return;
    // Column B = Exercise name — rename everywhere when it changes
    if (e.range.getColumn() === 2 && e.oldValue && e.value) {
      var oldName = String(e.oldValue).trim();
      var newName = String(e.value).trim();
      if (oldName && newName && oldName.toLowerCase() !== newName.toLowerCase()) {
        renameExerciseEverywhere_(oldName, newName);
      }
    }
    refreshMuscleExerciseDropdowns_();
    try {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        'Exercises updated. Refresh the sidebar to see the new name.',
        'LiftLogic',
        5
      );
    } catch (err) {
      // ignore
    }
    return;
  }

  if (MUSCLE_TABS.indexOf(sheetName) === -1) return;
  if (e.range.getRow() === 1) return;

  var previousExercise = '';
  if (e.range.getColumn() === 2 && e.oldValue) {
    previousExercise = String(e.oldValue).trim();
  }

  syncRow_(sheet, e.range.getRow(), sheetName);

  if (previousExercise) {
    maybeRemoveUnusedCustomExercise_(previousExercise);
  }

  refreshDashboard();
}

// ---------------------------------------------------------------------------
// Interactive Dashboard
// ---------------------------------------------------------------------------

function refreshExerciseDropdowns() {
  refreshMuscleExerciseDropdowns_();
  try {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Dropdowns now match the Exercises sheet (deletions included). Refresh the sidebar to update it too.',
      'LiftLogic',
      6
    );
  } catch (e) {
    // toast unavailable outside UI context
  }
}

function importExercisesFromMuscleTabs() {
  var before = buildLogCatalog_().length;
  syncExercisesFromMuscleTabs_();
  refreshMuscleExerciseDropdowns_();
  var after = buildLogCatalog_().length;
  try {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Imported from muscle tabs. Catalog size: ' + before + ' → ' + after + '.',
      'LiftLogic',
      6
    );
  } catch (e) {
    // ignore
  }
}

function pruneUnusedCustomExercises() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(EXERCISES);
  if (!sheet) return;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return;
  var data = readBlock_(sheet, 2, 1, lastRow, 2);
  var removed = 0;
  for (var i = data.length - 1; i >= 0; i--) {
    var name = String(data[i][1] || '').trim();
    if (!name || isSeedExercise_(name)) continue;
    if (isExerciseUsedAnywhere_(name)) continue;
    sheet.deleteRow(i + 2);
    removed++;
  }
  refreshMuscleExerciseDropdowns_();
  try {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      'Removed ' + removed + ' unused custom exercise(s). Refresh the sidebar.',
      'LiftLogic',
      6
    );
  } catch (e) {
    // ignore
  }
}

function refreshMuscleExerciseDropdowns_() {
  // Rebuild lists strictly from the Exercises sheet.
  // Deleting a row there removes it from dropdowns; it is NOT re-added from logs.
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var byMuscle = exercisesByMuscleFromSheet_();

  MUSCLE_TABS.forEach(function (muscle) {
    var sheet = ss.getSheetByName(muscle);
    if (!sheet) return;
    var names = byMuscle[muscle] || [];
    if (!names.length) {
      getRangeBlock_(sheet, 2, 2, 998, 1).clearDataValidations();
      return;
    }
    var rule = SpreadsheetApp.newDataValidation()
      .requireValueInList(names, true)
      .setAllowInvalid(true)
      .build();
    getRangeBlock_(sheet, 2, 2, 998, 1).setDataValidation(rule);
  });
}

function refreshDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var dash = ss.getSheetByName(DASHBOARD);
  var logSheet = ss.getSheetByName(WORKOUT_LOG);
  if (!dash || !logSheet) return;

  ensureDashboardControls_(dash);
  refreshMuscleExerciseDropdowns_();

  var muscle = String(dash.getRange(DASHBOARD_CFG.MUSCLE).getValue() || 'All').trim();
  var view = String(dash.getRange(DASHBOARD_CFG.VIEW).getValue() || 'Summary').trim();
  var searchRaw = String(dash.getRange(DASHBOARD_CFG.SEARCH).getValue() || '').trim();
  var search = normalizeSearch_(searchRaw);
  var exerciseFilter = String(dash.getRange(DASHBOARD_CFG.EXERCISE).getValue() || 'All').trim();

  var allEntries = readWorkoutLog_(logSheet);
  var filtered = filterEntries_(allEntries, muscle, search, exerciseFilter);

  updateExerciseDropdown_(dash, allEntries, muscle, exerciseFilter);
  writeKpis_(dash, filtered);
  writeSectionTitle_(dash, muscle, view, filtered);
  writeTable_(dash, view, filtered);

  var now = new Date();
  var timestamp = formatDate_(now) + ' ' +
    String(now.getHours()).padStart(2, '0') + ':' +
    String(now.getMinutes()).padStart(2, '0');
  dash.getRange('A2').setValue(
    'Live · synced from muscle tabs · refreshed ' + timestamp
  );
}

function ensureDashboardControls_(dash) {
  var muscle = String(dash.getRange(DASHBOARD_CFG.MUSCLE).getValue() || '').trim();
  if (MUSCLE_TABS.indexOf(muscle) === -1 && muscle !== 'All') {
    dash.getRange(DASHBOARD_CFG.MUSCLE).setValue('All');
  }
  var view = String(dash.getRange(DASHBOARD_CFG.VIEW).getValue() || '').trim();
  if (view !== 'Summary' && view !== 'Workout Log') {
    dash.getRange(DASHBOARD_CFG.VIEW).setValue('Summary');
  }
  // Clear legacy fake-placeholder text from older formats
  var searchCell = dash.getRange(DASHBOARD_CFG.SEARCH);
  var search = String(searchCell.getValue() || '').trim().toLowerCase();
  if (!search || search.indexOf('type to filter') === 0) {
    searchCell.clearContent();
  }
  if (!searchCell.getNote()) {
    searchCell.setNote(DASHBOARD_CFG.SEARCH_HINT);
  }
  // SEARCH is free text — remove any dropdown validation copied from VIEW by mistake
  dash.getRange('E3:G3').clearDataValidations();
}

// ---------------------------------------------------------------------------
// HTML Sidebar API
// ---------------------------------------------------------------------------

function normalizeTrackerFilters_(filters) {
  filters = filters || {};
  var muscle = String(filters.muscle || 'All').trim() || 'All';
  if (MUSCLE_TABS.indexOf(muscle) === -1 && muscle !== 'All') {
    muscle = 'All';
  }
  var view = String(filters.view || 'Summary').trim() || 'Summary';
  if (view !== 'Summary' && view !== 'Workout Log') {
    view = 'Summary';
  }
  return {
    muscle: muscle,
    view: view,
    search: normalizeSearch_(String(filters.search || '').trim()),
    exercise: String(filters.exercise || 'All').trim() || 'All',
  };
}

function normalizeSearch_(raw) {
  var text = String(raw || '').trim();
  if (!text) return '';
  var lower = text.toLowerCase();
  if (lower.indexOf('type to filter') === 0) return '';
  if (lower.indexOf('exercise or notes') === 0) return '';
  return lower;
}

function readDashboardFilters_() {
  var dash = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(DASHBOARD);
  if (!dash) {
    return normalizeTrackerFilters_({});
  }
  return normalizeTrackerFilters_({
    muscle: dash.getRange(DASHBOARD_CFG.MUSCLE).getValue(),
    view: dash.getRange(DASHBOARD_CFG.VIEW).getValue(),
    search: dash.getRange(DASHBOARD_CFG.SEARCH).getValue(),
    exercise: dash.getRange(DASHBOARD_CFG.EXERCISE).getValue(),
  });
}

function writeDashboardFilters_(filters) {
  var dash = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(DASHBOARD);
  if (!dash) return;
  dash.getRange(DASHBOARD_CFG.MUSCLE).setValue(filters.muscle);
  dash.getRange(DASHBOARD_CFG.VIEW).setValue(filters.view);
  dash.getRange(DASHBOARD_CFG.SEARCH).setValue(filters.search || '');
  dash.getRange(DASHBOARD_CFG.EXERCISE).setValue(filters.exercise);
}

function getTrackerPayload_(filters, options) {
  options = options || {};
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(WORKOUT_LOG);
  if (!logSheet) {
    return emptyTrackerPayload_(filters);
  }

  var allEntries = readWorkoutLog_(logSheet);
  var searchLower = filters.search.toLowerCase();
  var filtered = filterEntries_(allEntries, filters.muscle, searchLower, filters.exercise);

  var exercisePool = allEntries;
  if (filters.muscle && filters.muscle !== 'All') {
    exercisePool = exercisePool.filter(function (e) { return e.muscle === filters.muscle; });
  }
  var exerciseOptions = ['All'].concat(
    uniqueStrings_(exercisePool.map(function (e) { return e.exercise; })).sort()
  );

  var kpis = computeKpis_(filtered);
  var sectionTitle = buildSectionTitle_(filters.muscle, filters.view, filtered);
  var table = buildTrackerTable_(filters.view, filtered);
  var now = new Date();
  var refreshedAt = formatDate_(now) + ' ' +
    String(now.getHours()).padStart(2, '0') + ':' +
    String(now.getMinutes()).padStart(2, '0');

  return {
    muscles: ['All'].concat(MUSCLE_TABS),
    exercises: exerciseOptions,
    logCatalog: buildLogCatalog_(),
    filters: filters,
    kpis: kpis,
    sectionTitle: sectionTitle,
    headers: table.headers,
    rows: table.rows,
    refreshedAt: refreshedAt,
  };
}

function emptyTrackerPayload_(filters) {
  return {
    muscles: ['All'].concat(MUSCLE_TABS),
    exercises: ['All'],
    logCatalog: buildLogCatalog_(),
    filters: filters,
    kpis: { exercises: 0, entries: 0, topLift: 0, topLiftExercise: '' },
    sectionTitle: 'No workout data',
    headers: [],
    rows: [],
    refreshedAt: '',
  };
}

function buildLogCatalog_() {
  // Exercises sheet is the source of truth (same list as muscle-tab dropdowns).
  var metricByName = {};
  EXERCISE_CATALOG.forEach(function (ex) {
    metricByName[ex.name] = ex.metric;
  });

  var byName = {};
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(EXERCISES);
  if (sheet) {
    var lastRow = sheet.getLastRow();
    if (lastRow >= 2) {
      var data = readBlock_(sheet, 2, 1, lastRow, 3);
      data.forEach(function (row) {
        var name = String(row[1] || '').trim();
        var muscle = String(row[2] || '').trim();
        if (!name || MUSCLE_TABS.indexOf(muscle) === -1) return;
        byName[name] = {
          name: name,
          muscle: muscle,
          metric: metricByName[name] || (muscle === 'Cardio' ? 'units' : 'lb'),
        };
      });
    }
  }

  // Fallback if Exercises sheet is empty / missing
  if (!Object.keys(byName).length) {
    EXERCISE_CATALOG.forEach(function (ex) {
      byName[ex.name] = {
        name: ex.name,
        muscle: ex.muscle,
        metric: ex.metric,
      };
    });
  }

  return Object.keys(byName).sort().map(function (key) { return byName[key]; });
}

function exercisesByMuscleFromSheet_() {
  var grouped = {};
  MUSCLE_TABS.forEach(function (m) { grouped[m] = []; });

  buildLogCatalog_().forEach(function (ex) {
    if (!grouped[ex.muscle]) grouped[ex.muscle] = [];
    grouped[ex.muscle].push(ex.name);
  });

  MUSCLE_TABS.forEach(function (m) {
    grouped[m] = uniqueStrings_(grouped[m]).sort();
  });
  return grouped;
}

function syncExercisesFromMuscleTabs_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  MUSCLE_TABS.forEach(function (muscle) {
    var sheet = ss.getSheetByName(muscle);
    if (!sheet) return;
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) return;
    var names = readBlock_(sheet, 2, 2, lastRow, 1);
    for (var i = 0; i < names.length; i++) {
      var name = String(names[i][0] || '').trim();
      if (name) ensureExerciseInCatalog_(name, muscle);
    }
  });
}

/**
 * Rename an exercise across muscle tabs, Workout_Log, and Goals.
 * Triggered when the Exercises sheet name (column B) is edited.
 */
function renameExerciseEverywhere_(oldName, newName) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var oldLower = String(oldName).trim().toLowerCase();
  var nextName = String(newName).trim();
  if (!oldLower || !nextName) return;

  // Muscle tabs — Exercise column B
  MUSCLE_TABS.forEach(function (muscle) {
    var sheet = ss.getSheetByName(muscle);
    if (!sheet) return;
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) return;
    var range = getRangeBlock_(sheet, 2, 2, lastRow - 1, 1);
    var values = range.getValues();
    var changed = false;
    for (var i = 0; i < values.length; i++) {
      if (String(values[i][0] || '').trim().toLowerCase() === oldLower) {
        values[i][0] = nextName;
        changed = true;
      }
    }
    if (changed) range.setValues(values);
  });

  // Workout_Log — Exercise column E (index 5 / col 5)
  var logSheet = ss.getSheetByName(WORKOUT_LOG);
  if (logSheet) {
    var logLast = logSheet.getLastRow();
    if (logLast >= 2) {
      var logRange = getRangeBlock_(logSheet, 2, LOG_COLUMNS.EXERCISE + 1, logLast - 1, 1);
      var logValues = logRange.getValues();
      var logChanged = false;
      for (var j = 0; j < logValues.length; j++) {
        if (String(logValues[j][0] || '').trim().toLowerCase() === oldLower) {
          logValues[j][0] = nextName;
          logChanged = true;
        }
      }
      if (logChanged) logRange.setValues(logValues);
    }
  }

  // Goals — Exercise column C (index 3)
  var goalsSheet = ss.getSheetByName('Goals');
  if (goalsSheet) {
    var goalsLast = goalsSheet.getLastRow();
    if (goalsLast >= 2) {
      var goalsRange = getRangeBlock_(goalsSheet, 2, 3, goalsLast - 1, 1);
      var goalsValues = goalsRange.getValues();
      var goalsChanged = false;
      for (var k = 0; k < goalsValues.length; k++) {
        if (String(goalsValues[k][0] || '').trim().toLowerCase() === oldLower) {
          goalsValues[k][0] = nextName;
          goalsChanged = true;
        }
      }
      if (goalsChanged) goalsRange.setValues(goalsValues);
    }
  }
}

function metricFor_(exercise, muscle) {
  var name = String(exercise || '').trim();
  for (var i = 0; i < EXERCISE_CATALOG.length; i++) {
    if (EXERCISE_CATALOG[i].name === name) {
      return EXERCISE_CATALOG[i].metric;
    }
  }
  if (muscle === 'Cardio') return 'units';
  return 'lb';
}

function computeKpis_(entries) {
  var exercises = uniqueStrings_(entries.map(function (e) { return e.exercise; }));
  var top = computeTopLift_(entries);
  return {
    exercises: exercises.length,
    entries: entries.length,
    topLift: top.value || 0,
    topLiftExercise: top.exercise || '',
  };
}

function buildSectionTitle_(muscle, view, entries) {
  var muscleLabel = muscle && muscle !== 'All' ? muscle : 'All muscles';
  var exerciseCount = uniqueStrings_(entries.map(function (e) { return e.exercise; })).length;
  if (view === 'Workout Log') {
    return muscleLabel + ' — Workout Log (' + entries.length + ' entries)';
  }
  return muscleLabel + ' — Summary Records (' + exerciseCount + ' exercises)';
}

function buildTrackerTable_(view, entries) {
  if (view === 'Workout Log') {
    var logRows = entries.slice().sort(function (a, b) {
      return new Date(b.date) - new Date(a.date);
    }).map(function (e) {
      return [
        formatDate_(e.date),
        e.muscle,
        e.exercise,
        formatMetricValue_(e),
        unitFor_(e),
        e.notes,
      ];
    });
    return {
      headers: ['Date', 'Muscle', 'Exercise', 'Value', 'Unit', 'Notes'],
      rows: logRows,
    };
  }

  var summaryRows = buildSummaryRows_(entries).map(function (row) {
    var entry = { exercise: row[0], weight: row[1], muscle: row[4], date: row[2], notes: row[3] };
    return [
      row[0],
      formatMetricValue_(entry),
      unitFor_(entry),
      formatDate_(row[2]),
      row[3],
    ];
  });
  return {
    headers: ['Exercise', 'Best', 'Unit', 'Date', 'Notes'],
    rows: summaryRows,
  };
}

function formatDate_(dateVal) {
  if (!dateVal) return '';
  var d = dateVal instanceof Date ? dateVal : new Date(dateVal);
  if (isNaN(d.getTime())) return String(dateVal);

  // Google Sheets date-only cells arrive at UTC midnight; local getDate() shifts back a day.
  if (
    d.getUTCHours() === 0 &&
    d.getUTCMinutes() === 0 &&
    d.getUTCSeconds() === 0 &&
    d.getUTCMilliseconds() === 0
  ) {
    var noonUtc = new Date(d.getTime() + 12 * 60 * 60 * 1000);
    var y = noonUtc.getUTCFullYear();
    var m = String(noonUtc.getUTCMonth() + 1).padStart(2, '0');
    var day = String(noonUtc.getUTCDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, '0');
  var day = String(d.getDate()).padStart(2, '0');
  return y + '-' + m + '-' + day;
}

function readWorkoutLog_(logSheet) {
  var lastRow = logSheet.getLastRow();
  if (lastRow < 2) return [];

  var data = readBlock_(logSheet, 2, 1, lastRow, 8);
  var entries = [];
  for (var i = 0; i < data.length; i++) {
    var row = data[i];
    var dateVal = row[LOG_COLUMNS.DATE];
    var exercise = String(row[LOG_COLUMNS.EXERCISE] || '').trim();
    if (!dateVal || !exercise) continue;
    entries.push({
      date: dateVal,
      muscle: String(row[LOG_COLUMNS.MUSCLE] || ''),
      exercise: exercise,
      weight: Number(row[LOG_COLUMNS.WEIGHT]),
      notes: String(row[LOG_COLUMNS.NOTES] || '').trim(),
    });
  }
  return entries;
}

function filterEntries_(entries, muscle, search, exerciseFilter) {
  return entries.filter(function (entry) {
    if (muscle && muscle !== 'All' && entry.muscle !== muscle) return false;
    if (exerciseFilter && exerciseFilter !== 'All' && entry.exercise !== exerciseFilter) {
      return false;
    }
    if (search) {
      var haystack = (entry.exercise + ' ' + entry.notes + ' ' + entry.muscle).toLowerCase();
      if (haystack.indexOf(search) === -1) return false;
    }
    return true;
  });
}

function updateExerciseDropdown_(dash, allEntries, muscle, currentExercise) {
  var pool = allEntries;
  if (muscle && muscle !== 'All') {
    pool = pool.filter(function (e) { return e.muscle === muscle; });
  }
  var exercises = uniqueStrings_(pool.map(function (e) { return e.exercise; })).sort();
  var options = ['All'].concat(exercises);

  if (currentExercise !== 'All' && options.indexOf(currentExercise) === -1) {
    dash.getRange(DASHBOARD_CFG.EXERCISE).setValue('All');
  }

  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(options, true)
    .setAllowInvalid(false)
    .build();
  dash.getRange(DASHBOARD_CFG.EXERCISE).setDataValidation(rule);
}

function writeKpis_(dash, entries) {
  var kpis = computeKpis_(entries);
  dash.getRange(DASHBOARD_CFG.KPI_EXERCISES).setValue(kpis.exercises);
  dash.getRange(DASHBOARD_CFG.KPI_ENTRIES).setValue(kpis.entries);
  if (kpis.topLift > 0) {
    dash.getRange(DASHBOARD_CFG.KPI_TOPLIFT).setValue(kpis.topLift);
    dash.getRange(DASHBOARD_CFG.KPI_TOPLIFT_EXERCISE).setValue(kpis.topLiftExercise || '');
  } else {
    dash.getRange(DASHBOARD_CFG.KPI_TOPLIFT).setValue('—');
    dash.getRange(DASHBOARD_CFG.KPI_TOPLIFT_EXERCISE).setValue('');
  }
}

function writeSectionTitle_(dash, muscle, view, entries) {
  dash.getRange(DASHBOARD_CFG.SECTION_TITLE).setValue(
    buildSectionTitle_(muscle, view, entries)
  );
}

function writeTable_(dash, view, entries) {
  unmergeDashboardTable_(dash);
  clearDataArea_(dash);
  var table = buildTrackerTable_(view, entries);

  if (table.headers.length) {
    writeBlock_(dash, DASHBOARD_CFG.HEADER_ROW, 1, [table.headers]);
  }

  if (table.rows.length) {
    writeBlock_(dash, DASHBOARD_CFG.DATA_START_ROW, 1, table.rows);
  }
}

function buildSummaryRows_(entries) {
  var bestByExercise = {};
  entries.forEach(function (entry) {
    var key = entry.exercise;
    var current = bestByExercise[key];
    if (!current || entry.weight > current.weight ||
        (entry.weight === current.weight && new Date(entry.date) > new Date(current.date))) {
      bestByExercise[key] = entry;
    }
  });
  return Object.keys(bestByExercise).sort().map(function (name) {
    var best = bestByExercise[name];
    return [best.exercise, best.weight, best.date, best.notes, best.muscle];
  });
}

function unitFor_(entry) {
  if (!entry) return 'lb';
  return metricFor_(entry.exercise, entry.muscle);
}

function formatMetricValue_(entry) {
  var n = Number(entry.weight);
  if (isNaN(n)) return entry.weight;
  var unit = unitFor_(entry);
  if (unit === 'steps') {
    return Math.round(n).toLocaleString();
  }
  if (n % 1 === 0) return String(n);
  return String(Math.round(n * 10) / 10);
}

function computeTopLift_(entries) {
  // Strength loads only — exclude cardio minutes/steps and bodyweight reps
  var strength = entries.filter(function (e) {
    return metricFor_(e.exercise, e.muscle) === 'lb' && e.weight > 0;
  });
  if (!strength.length) return { value: 0, exercise: '' };

  var top = strength[0];
  strength.forEach(function (e) {
    if (e.weight > top.weight) top = e;
  });
  return { value: top.weight, exercise: top.exercise };
}

function clearDataArea_(dash) {
  var rows = DASHBOARD_CFG.MAX_DATA_ROWS;
  var cols = DASHBOARD_CFG.DATA_COLS;
  getRangeBlock_(dash, DASHBOARD_CFG.DATA_START_ROW, 1, rows, cols).clearContent();
  getRangeBlock_(dash, DASHBOARD_CFG.HEADER_ROW, 1, 1, cols).clearContent();
}

function unmergeDashboardTable_(dash) {
  // getMergedRanges() exists on Range, not Sheet.
  var startRow = DASHBOARD_CFG.HEADER_ROW;
  var numRows = DASHBOARD_CFG.MAX_DATA_ROWS + 1;
  var block = getRangeBlock_(dash, startRow, 1, numRows, DASHBOARD_CFG.DATA_COLS);
  block.getMergedRanges().forEach(function (range) {
    range.breakApart();
  });
}

function isDashboardControlEdit_(a1) {
  return DASHBOARD_CONTROL_CELLS.indexOf(a1) !== -1;
}

function uniqueStrings_(values) {
  var seen = {};
  var result = [];
  values.forEach(function (v) {
    var key = String(v).trim();
    if (!key || seen[key]) return;
    seen[key] = true;
    result.push(key);
  });
  return result;
}

// ---------------------------------------------------------------------------
// Muscle tab → Workout_Log sync
// ---------------------------------------------------------------------------

function syncAllMuscleTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  MUSCLE_TABS.forEach(function (muscle) {
    var sheet = ss.getSheetByName(muscle);
    if (!sheet) return;
    var lastRow = sheet.getLastRow();
    for (var row = 2; row <= lastRow; row++) {
      syncRow_(sheet, row, muscle);
    }
  });
  refreshDashboard();
}

function syncRow_(sheet, row, muscle) {
  var values = readRow_(sheet, row, 4);
  var dateVal = values[ENTRY_COLUMNS.DATE];
  var exercise = String(values[ENTRY_COLUMNS.EXERCISE] || '').trim();
  var weight = values[ENTRY_COLUMNS.WEIGHT];
  var notes = String(values[ENTRY_COLUMNS.NOTES] || '').trim();
  var sourceRow = muscle + '!A' + row;

  var logSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(WORKOUT_LOG);
  if (!logSheet) throw new Error('Missing Workout_Log sheet');

  var existingRow = findLogRowBySource_(logSheet, sourceRow);

  if (!dateVal && !exercise && !weight && !notes) {
    if (existingRow > 0) {
      var loggedExercise = String(
        logSheet.getRange(existingRow, LOG_COLUMNS.EXERCISE + 1).getValue() || ''
      ).trim();
      logSheet.deleteRow(existingRow);
      if (loggedExercise) {
        maybeRemoveUnusedCustomExercise_(loggedExercise);
      }
    }
    return;
  }

  // Add new exercise names to the Exercises sheet immediately (even if the
  // row is still incomplete — date/weight come later).
  var catalogInfo = null;
  if (exercise) {
    catalogInfo = ensureExerciseInCatalog_(exercise, muscle);
  }

  if (!dateVal || !exercise) return;
  if (!isValidWeight_(weight, muscle, exercise)) return;

  var exerciseId = (catalogInfo && catalogInfo.id) ? catalogInfo.id : '';
  if (!exerciseId) {
    var lookedUp = lookupExercise_(exercise);
    exerciseId = lookedUp ? lookedUp.id : '';
  }
  var logId = existingRow > 0
    ? logSheet.getRange(existingRow, LOG_COLUMNS.LOG_ID + 1).getValue()
    : nextLogId_(logSheet);

  var record = [
    logId,
    dateVal,
    muscle,
    exerciseId,
    exercise,
    weight,
    notes,
    sourceRow,
  ];

  if (existingRow > 0) {
    writeRow_(logSheet, existingRow, record);
  } else {
    logSheet.appendRow(record);
  }
}

function findLogRowBySource_(logSheet, sourceRow) {
  var lastRow = logSheet.getLastRow();
  if (lastRow < 2) return -1;

  var sources = readBlock_(logSheet, 2, LOG_COLUMNS.SOURCE_ROW + 1, lastRow, 1);
  for (var i = 0; i < sources.length; i++) {
    if (String(sources[i][0]) === sourceRow) {
      return i + 2;
    }
  }
  return -1;
}

function isSeedExercise_(name) {
  var normalized = String(name || '').trim().toLowerCase();
  if (!normalized) return false;
  for (var i = 0; i < EXERCISE_CATALOG.length; i++) {
    if (EXERCISE_CATALOG[i].name.toLowerCase() === normalized) return true;
  }
  return false;
}

function isExerciseUsedAnywhere_(name) {
  var normalized = String(name || '').trim().toLowerCase();
  if (!normalized) return false;
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  for (var m = 0; m < MUSCLE_TABS.length; m++) {
    var sheet = ss.getSheetByName(MUSCLE_TABS[m]);
    if (!sheet) continue;
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) continue;
    var names = readBlock_(sheet, 2, 2, lastRow, 1);
    for (var i = 0; i < names.length; i++) {
      if (String(names[i][0] || '').trim().toLowerCase() === normalized) {
        return true;
      }
    }
  }

  var logSheet = ss.getSheetByName(WORKOUT_LOG);
  if (logSheet) {
    var logLast = logSheet.getLastRow();
    if (logLast >= 2) {
      var logNames = readBlock_(logSheet, 2, LOG_COLUMNS.EXERCISE + 1, logLast, 1);
      for (var j = 0; j < logNames.length; j++) {
        if (String(logNames[j][0] || '').trim().toLowerCase() === normalized) {
          return true;
        }
      }
    }
  }

  var goalsSheet = ss.getSheetByName('Goals');
  if (goalsSheet) {
    var goalsLast = goalsSheet.getLastRow();
    if (goalsLast >= 2) {
      var goalNames = readBlock_(goalsSheet, 2, 3, goalsLast, 1);
      for (var k = 0; k < goalNames.length; k++) {
        if (String(goalNames[k][0] || '').trim().toLowerCase() === normalized) {
          return true;
        }
      }
    }
  }

  return false;
}

function removeExerciseFromCatalog_(name) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(EXERCISES);
  if (!sheet) return false;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return false;
  var normalized = String(name || '').trim().toLowerCase();
  var data = readBlock_(sheet, 2, 1, lastRow, 2);
  for (var i = data.length - 1; i >= 0; i--) {
    if (String(data[i][1] || '').trim().toLowerCase() === normalized) {
      sheet.deleteRow(i + 2);
      return true;
    }
  }
  return false;
}

/**
 * After a custom exercise is cleared/replaced on a muscle tab, drop it from
 * the Exercises sheet if nothing else references it. Seed catalog stays.
 */
function maybeRemoveUnusedCustomExercise_(name) {
  var clean = String(name || '').trim();
  if (!clean || isSeedExercise_(clean)) return;
  if (isExerciseUsedAnywhere_(clean)) return;
  if (removeExerciseFromCatalog_(clean)) {
    refreshMuscleExerciseDropdowns_();
  }
}

function ensureExerciseInCatalog_(name, muscle) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(EXERCISES);
  if (!sheet) {
    throw new Error('Missing Exercises sheet');
  }

  var cleanName = String(name || '').trim();
  var cleanMuscle = String(muscle || '').trim();
  if (!cleanName || MUSCLE_TABS.indexOf(cleanMuscle) === -1) {
    return null;
  }

  var lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    var data = readBlock_(sheet, 2, 1, lastRow, 3);
    var normalized = cleanName.toLowerCase();
    for (var i = 0; i < data.length; i++) {
      if (String(data[i][1]).trim().toLowerCase() === normalized) {
        return {
          id: String(data[i][0] || '').trim(),
          name: String(data[i][1] || '').trim(),
          added: false,
          updated: false,
        };
      }
    }
  }

  var id = nextExerciseId_(sheet, cleanMuscle);
  sheet.appendRow([id, cleanName, cleanMuscle, '', '']);
  return { id: id, name: cleanName, added: true, updated: false };
}

function nextExerciseId_(sheet, muscle) {
  var prefixes = {
    Chest: 'CH',
    Back: 'BK',
    Shoulders: 'SH',
    Biceps: 'BI',
    Triceps: 'TR',
    Legs: 'LG',
    Cardio: 'CD',
  };
  var prefix = prefixes[muscle] || 'EX';
  var lastRow = sheet.getLastRow();
  var maxNum = 0;
  if (lastRow >= 2) {
    var ids = readBlock_(sheet, 2, 1, lastRow, 1);
    var re = new RegExp('^' + prefix + '(\\d+)$', 'i');
    ids.forEach(function (row) {
      var match = String(row[0]).match(re);
      if (match) {
        maxNum = Math.max(maxNum, parseInt(match[1], 10));
      }
    });
  }
  return prefix + String(maxNum + 1).padStart(3, '0');
}

function lookupExercise_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(EXERCISES);
  if (!sheet) return null;

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;

  var data = readBlock_(sheet, 2, 1, lastRow, 2);
  var normalized = String(name).trim().toLowerCase();
  for (var i = 0; i < data.length; i++) {
    if (String(data[i][1]).trim().toLowerCase() === normalized) {
      return { id: data[i][0], name: data[i][1] };
    }
  }
  return null;
}

function nextLogId_(logSheet) {
  var lastRow = logSheet.getLastRow();
  if (lastRow < 2) return 'L000001';

  var ids = readBlock_(logSheet, 2, LOG_COLUMNS.LOG_ID + 1, lastRow, 1);
  var maxNum = 0;
  ids.forEach(function (row) {
    var match = String(row[0]).match(/^L(\d+)$/);
    if (match) {
      maxNum = Math.max(maxNum, parseInt(match[1], 10));
    }
  });
  return 'L' + String(maxNum + 1).padStart(6, '0');
}

function isValidWeight_(weight, muscle, exercise) {
  if (weight === '' || weight === null || weight === undefined) {
    return false;
  }
  var num = Number(weight);
  if (isNaN(num) || num < 0) {
    return false;
  }
  var metric = metricFor_(exercise || '', muscle);
  // lb / reps / steps / minutes all require a positive logged value
  if (metric === 'lb' || metric === 'reps' || metric === 'steps' || metric === 'minutes') {
    return num > 0;
  }
  return num >= 0;
}

// ---------------------------------------------------------------------------
// Range helpers — Apps Script 4-arg form is (startRow, startCol, numRows, numCols)
// ---------------------------------------------------------------------------

function getRangeBlock_(sheet, startRow, startCol, numRows, numCols) {
  return sheet.getRange(startRow, startCol, numRows, numCols);
}

function readBlock_(sheet, startRow, startCol, endRow, numCols) {
  var numRows = endRow - startRow + 1;
  if (numRows <= 0) return [];
  return sheet.getRange(startRow, startCol, numRows, numCols).getValues();
}

function writeBlock_(sheet, startRow, startCol, rows) {
  if (!rows || !rows.length) return;
  sheet.getRange(startRow, startCol, rows.length, rows[0].length).setValues(rows);
}

function readRow_(sheet, row, numCols) {
  return sheet.getRange(row, 1, 1, numCols).getValues()[0];
}

function writeRow_(sheet, row, values) {
  sheet.getRange(row, 1, 1, values.length).setValues([values]);
}
