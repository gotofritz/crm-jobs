// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var StateToSheetBridge = /** @class */ (function () {
    function StateToSheetBridge(_a) {
        var _b = _a.fields, fields = _b === void 0 ? [] : _b, _c = _a.colBg, colBg = _c === void 0 ? COL_BG_DEFAULT : _c, _d = _a.colFg, colFg = _d === void 0 ? COL_FG_DEFAULT : _d, _e = _a.vAlign, vAlign = _e === void 0 ? DEFAULT_VALIGN : _e, _f = _a.state, state = _f === void 0 ? "" : _f;
        this.fields = [];
        this.colBg = COL_BG_DEFAULT;
        this.colFg = COL_FG_DEFAULT;
        this.vAlign = DEFAULT_VALIGN;
        this.fields = fields;
        this.fieldNames = this.fields.reduce(function (accumulator, _a, i) {
            var name = _a.name;
            accumulator[name] = i;
            return accumulator;
        }, {});
        this.fields.slice(0, -1).forEach(function (field) {
            if (!field.separator)
                throw Error("Error: fields must have a separator");
        });
        this.colBg = colBg;
        this.colFg = colFg;
        this.vAlign = vAlign;
        this.stateName_ = state;
        this.parser = this.generateParsingRegexp();
    }
    StateToSheetBridge.prototype.asJson = function () {
        var jsonRepresentation = this.stateName_
            ? {
                state: this.stateName_,
                colBg: this.colBg,
                colFg: this.colFg
            }
            : {};
        for (var _i = 0, _a = this.fields; _i < _a.length; _i++) {
            var _b = _a[_i], name = _b.name, value = _b.value;
            jsonRepresentation[name] = value;
        }
        return jsonRepresentation;
    };
    StateToSheetBridge.prototype.asPlainText = function () {
        return this.fields.reduce(function (accumulator, _a) {
            var value = _a.value, separator = _a.separator;
            return accumulator + value + separator;
        }, "");
    };
    StateToSheetBridge.prototype.generateParsingRegexp = function () {
        var parser = new RegExp(this.fields.reduce(function (accumulator, _a, i, arr) {
            var separator = _a.separator;
            return i === arr.length - 1
                ? "".concat(accumulator, "(.*)").concat(separator)
                : "".concat(accumulator, "(.*?)").concat(separator);
        }, "^") + "$", "sm");
        return parser;
    };
    StateToSheetBridge.prototype.getFieldValue = function (nameOfField, fallback) {
        if (fallback === void 0) { fallback = ""; }
        if (nameOfField in this.fieldNames) {
            return this.fields[this.fieldNames[nameOfField]].value;
        }
        return fallback;
    };
    StateToSheetBridge.prototype.loadFromSheet = function (cell) {
        this.loadTextDataFromSheet(cell);
        this.loadStateDataFromSheet(cell);
        return this;
    };
    StateToSheetBridge.prototype.loadStateDataFromSheet = function (cell) {
        if (!this.stateName_)
            return;
        this.state = getBgColor(cell);
        return;
    };
    Object.defineProperty(StateToSheetBridge.prototype, "state", {
        get: function () {
            return this.stateName_;
        },
        set: function (stateName) {
            // if stateName_ is falsy, it means this is stateless, so we don't care
            if (!stateName)
                return;
            try {
                var maybeState = getApp().states.asState(stateName);
                if (maybeState) {
                    this.colBg = maybeState === null || maybeState === void 0 ? void 0 : maybeState.bg;
                    this.colFg = maybeState === null || maybeState === void 0 ? void 0 : maybeState.fg;
                    this.stateName_ = maybeState === null || maybeState === void 0 ? void 0 : maybeState.name;
                }
                else {
                    this.stateName_ = "";
                }
            }
            catch (_a) {
                Logger.log("couldn't set state: ".concat(stateName));
                this.stateName_ = "";
            }
        },
        enumerable: false,
        configurable: true
    });
    StateToSheetBridge.prototype.loadTextDataFromSheet = function (cell) {
        var dataToParse = cell.getValue();
        if (!dataToParse)
            return;
        // GAS always tries to be helpful and convert strings to something else 🙄
        var dataAsString = asString(dataToParse);
        var matches = dataAsString.match(this.parser);
        if (!matches)
            return this;
        for (var i = 0, j = 1; i < this.fields.length && j < matches.length; i += 1, j += 1) {
            this.fields[i].value = matches[j];
        }
        return;
    };
    StateToSheetBridge.prototype.updateValues = function (fieldsData) {
        if (fieldsData === void 0) { fieldsData = {}; }
        for (var _i = 0, _a = this.fields; _i < _a.length; _i++) {
            var field = _a[_i];
            var name = field.name;
            field.updateValue(fieldsData[name]);
        }
    };
    StateToSheetBridge.prototype.updateCell = function (cell) {
        // get the whole text as one long string
        var wholeText = this.asPlainText();
        // create a RichText builder
        var richTextContent = SpreadsheetApp.newRichTextValue().setText(wholeText);
        // add markers at start end end of each field
        var startOffset = 0;
        for (var _i = 0, _a = this.fields; _i < _a.length; _i++) {
            var field = _a[_i];
            var value = field.value, style = field.style, separator = field.separator;
            var endOffset = Math.min(wholeText.length, startOffset + value.length + separator.length);
            // sometimes we get weird combinations which are hard to debug, so make sure
            // there is an actual string to handle
            if (startOffset !== endOffset) {
                richTextContent.setTextStyle(startOffset, endOffset, style);
            }
            startOffset = endOffset;
        }
        cell
            .setRichTextValue(richTextContent.build())
            .setVerticalAlignment(this.vAlign)
            .setBackground(this.colBg)
            .setFontColor(this.colFg)
            .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
        return this;
    };
    return StateToSheetBridge;
}());
