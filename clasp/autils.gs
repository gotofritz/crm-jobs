// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
/**
 * Convenience util
 */
var indexOfSelectedRow = function () { var _a, _b; return ((_b = (_a = SS === null || SS === void 0 ? void 0 : SS.getSelection()) === null || _a === void 0 ? void 0 : _a.getActiveRange()) === null || _b === void 0 ? void 0 : _b.getRow()) || -1; };
/**
 * Dies if there is no selection
 */
var dieUnlessSelection = function (msg) {
    if (msg === void 0) { msg = "You need to select a cell"; }
    a();
    b();
    if (!SS.getSelection()) {
        msgAndDie(msg);
    }
};
/**
 * @description if the user has selected something it will return the
 * index of the top row in the selection, otherwise it will show a
 * message box and stop
 * @param msg will be displayed in the message box
 * @param minRow allows
 * @returns
 */
var getSelectedRowOrDie = function (msg, excludeHeaderRow) {
    if (msg === void 0) { msg = "You need to select something on the sheet"; }
    if (excludeHeaderRow === void 0) { excludeHeaderRow = true; }
    var minRow = excludeHeaderRow ? DATA_ROW_START : 0;
    var maxRow = SS.getLastRow();
    var opportunityRow = indexOfSelectedRow();
    if (opportunityRow < minRow || opportunityRow > maxRow) {
        msgAndDie(msg);
    }
    return opportunityRow;
};
/**
 * the only way to send data to an HTML file in the sidebar is to
 * serialise it to a DOM fragment and append it to the document that
 * way
 *
 *
 */
var asHTMLfragment = function (jsonData, htmlId) {
    if (jsonData === void 0) { jsonData = {}; }
    if (htmlId === void 0) { htmlId = HTML_ID_EXTRA_FORM_DATA; }
    return "\n    <div style=\"display: block; background: pink\" id=\"".concat(htmlId, "\">\n      ").concat(JSON.stringify(jsonData), "\n    </div>\n  ");
};
var blackOnWhite = function () {
    return SpreadsheetApp.newColor()
        .setRgbColor("background-color: white; color: black")
        .build();
};
/**
 * @description Colors are a mess in GAS. Sometimes they are expressed
 * as RGB value, sometimes as one of the values in the palette. It's
 * not always obvious how that happens. This function normalises the two
 * @param cell this should be a range with a single cell, but in
 * practice it isn't validated, so it could be a range of any size. If
 * size > [1, 1] only the top left cell will be considered
 * @returns the color object from which to extract color information
 */
var isRGBColor = function (color) {
    return color.getColorType() === SpreadsheetApp.ColorType.RGB;
};
var getBgColor = function (cell) {
    var _a;
    var colorObj = isRGBColor(cell.getBackgroundObject())
        ? cell.getBackgroundObject()
        : ((_a = SS.getSpreadsheetTheme()) === null || _a === void 0 ? void 0 : _a.getConcreteColor(cell.getBackgroundObject().asThemeColor().getThemeColorType())) || blackOnWhite();
    return colorObj.asRgbColor().asHexString();
};
var getFgColor = function (cell) {
    var _a;
    var colorObj = isRGBColor(cell.getFontColorObject())
        ? cell.getFontColorObject()
        : ((_a = SS.getSpreadsheetTheme()) === null || _a === void 0 ? void 0 : _a.getConcreteColor(cell.getFontColorObject().asThemeColor().getThemeColorType())) || blackOnWhite();
    return colorObj.asRgbColor().asHexString();
};
var die = function (prompt) {
    throw Error(prompt);
};
/**
 * normalises date to yyyy-mm-dd
 */
var asString = function (aDate) {
    if (aDate instanceof Date) {
        return "".concat(aDate.getFullYear(), "-").concat(String(aDate.getMonth() + 1).padStart(2, "0"), "-").concat(String(aDate.getDate()).padStart(2, "0"));
    }
    return String(aDate);
};
/**
 * @description this is needed because Sheets 'helpfully' converts field
 * data to a different type with no discernible pattern
 * @param maybeDate the date we are testing
 * @param name the name of the field, for the error message
 * @throws if date is not valid
 * @return Date
 */
var validDate = function (maybeDate, name) {
    var maybeDateUnderTest = new Date(maybeDate);
    if (isNaN(maybeDateUnderTest.getTime())) {
        throw Error("".concat(name, " should be a valid date, but is ").concat(maybeDate));
    }
    return maybeDateUnderTest;
};
/**
 * @description this is needed because Sheets 'helpfully' converts field
 * data to a different type with no discernible pattern
 * @param maybeTime the string we are testing
 * @param name the name of the field, for the error message
 * @throws if time is not in HH:mm format
 * @return
 */
var validTime = function (maybeTime) {
    if (!maybeTime) {
        maybeTime = new Date();
    }
    if (maybeTime instanceof Date) {
        maybeTime =
            String(maybeTime.getHours()).padStart(2, "0") +
                ":" +
                String(maybeTime.getMinutes()).padStart(2, "0");
    }
    var maybeTimeUnderTest = String(maybeTime);
    if (/^\d\d:\d\d$/.test(maybeTimeUnderTest)) {
        return maybeTimeUnderTest;
    }
    throw Error("Should be a valid time in HH:mm format, but is ".concat(maybeTime));
};
var indexOfSelectedCol = function () {
    var _a, _b;
    return ((_b = (_a = SS.getSelection()) === null || _a === void 0 ? void 0 : _a.getActiveRange()) === null || _b === void 0 ? void 0 : _b.getColumn()) || -1;
};
var cellIsEmpty = function (row, col) {
    return col < 0
        ? true
        : valueIsEmpty(SS.getActiveSheet().getRange(row, col).getValue());
};
/**
 * Because GAS changes how empty cells are represented all the time
 * @returns
 */
var valueIsEmpty = function (couldBeEmpty) {
    return ["", null, undefined].includes(couldBeEmpty);
};
