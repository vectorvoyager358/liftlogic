/**
 * LiftLogic — sync muscle-tab entries to Workout_Log.
 *
 * Install: Extensions → Apps Script → paste this file → Save → Run setupTriggers
 */

var MUSCLE_TABS = ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Cardio'];
var WORKOUT_LOG = 'Workout_Log';
var EXERCISES = 'Exercises';

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
  if (MUSCLE_TABS.indexOf(sheetName) === -1) return;
  if (e.range.getRow() === 1) return;

  syncRow_(sheet, e.range.getRow(), sheetName);
}

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
}

function syncRow_(sheet, row, muscle) {
  var values = sheet.getRange(row, 1, row, 4).getValues()[0];
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
      logSheet.deleteRow(existingRow);
    }
    return;
  }

  if (!dateVal || !exercise) return;

  if (!isValidWeight_(weight, muscle)) return;

  var exerciseInfo = lookupExercise_(exercise);
  var exerciseId = exerciseInfo ? exerciseInfo.id : '';
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
    logSheet.getRange(existingRow, 1, 1, record.length).setValues([record]);
  } else {
    logSheet.appendRow(record);
  }
}

function findLogRowBySource_(logSheet, sourceRow) {
  var lastRow = logSheet.getLastRow();
  if (lastRow < 2) return -1;

  var sources = logSheet.getRange(2, LOG_COLUMNS.SOURCE_ROW + 1, lastRow - 1, 1).getValues();
  for (var i = 0; i < sources.length; i++) {
    if (String(sources[i][0]) === sourceRow) {
      return i + 2;
    }
  }
  return -1;
}

function lookupExercise_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(EXERCISES);
  if (!sheet) return null;

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;

  var data = sheet.getRange(2, 1, lastRow - 1, 2).getValues();
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

  var ids = logSheet.getRange(2, LOG_COLUMNS.LOG_ID + 1, lastRow - 1, 1).getValues();
  var maxNum = 0;
  ids.forEach(function (row) {
    var match = String(row[0]).match(/^L(\d+)$/);
    if (match) {
      maxNum = Math.max(maxNum, parseInt(match[1], 10));
    }
  });
  return 'L' + String(maxNum + 1).padStart(6, '0');
}

function isValidWeight_(weight, muscle) {
  if (weight === '' || weight === null || weight === undefined) {
    return false;
  }
  var num = Number(weight);
  if (isNaN(num) || num < 0) {
    return false;
  }
  if (muscle !== 'Cardio' && num === 0) {
    return false;
  }
  return true;
}
