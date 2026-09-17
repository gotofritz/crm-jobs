// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var SS = SpreadsheetApp.getActiveSpreadsheet();
var DATA_ROW_HEADER = 1;
var DATA_ROW_START = 2;
var DATA_COL_METAHEAD = 1;
var DATA_COL_METABODY = 2;
var DATA_COL_LATEST = 3;
var DATA_COL_STATES_START = 3;
var DEFAULT_VALIGN = "top";
var COL_BG_DEFAULT = "#ffffff";
var COL_FG_DEFAULT = "#000000";
var COL_BG_META = "#ffff00";
var COL_FG_META = "#000000";
var DIALOG_HEIGHT = 500;
var DIALOG_WIDTH = 800;
var HTML_ID_EXTRA_FORM_DATA = "fromSheet";
var bold = SpreadsheetApp.newTextStyle().setBold(true).build();
var italic = SpreadsheetApp.newTextStyle().setItalic(true).build();
var smaller = SpreadsheetApp.newTextStyle()
    .setBold(false)
    .setFontSize(9)
    .build();
var normal = SpreadsheetApp.newTextStyle()
    .setBold(false)
    .setItalic(false)
    .setFontSize(10)
    .build();
var HTML_NAME_EDIT_COMMENT = "forms/editCommentForm";
var HTML_NAME_OPPORTUNITY = "forms/formOpportunity";
var HTML_NAME_STEP = "forms/formStep";
var DEFAULT_OPPORTUNITY_SOURCE = "LinkedIn";
var DEFAULT_OPPORTUNITY_CONTACT = "(Contact unknown)";
var DEFAULT_STEP_TITLE = "Applied via site";
var DEFAULT_STEP_STATE = "UNREMARKABLE";
var a = function () { return Browser.msgBox("a"); };
function b() {
    Browser.msgBox("a");
}
