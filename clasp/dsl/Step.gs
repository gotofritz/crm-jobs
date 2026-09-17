// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __rest = (this && this.__rest) || function (s, e) {
    var t = {};
    for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
            if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
                t[p[i]] = s[p[i]];
        }
    return t;
};
var Step = /** @class */ (function () {
    function Step(_a) {
        var _b = _a.sh, sh = _b === void 0 ? SS.getActiveSheet() : _b, row = _a.row, _c = _a.col, col = _c === void 0 ? DATA_COL_LATEST : _c, stepData = _a.stepData, _d = _a.isNew, isNew = _d === void 0 ? false : _d;
        this.col = DATA_COL_LATEST;
        this.sh = sh;
        this.row = row;
        this.col = col;
        this.isNew = isNew;
        this.stepData = new StateToSheetBridge({
            state: DEFAULT_STEP_STATE,
            fields: [
                new Field({
                    name: "date",
                    separator: " __ ",
                    defaultValue: asString(new Date()),
                    style: bold
                }),
                new Field({
                    name: "time",
                    separator: "\n\n",
                    defaultValue: "",
                    style: bold
                }),
                new Field({
                    name: "title",
                    separator: "\n",
                    defaultValue: DEFAULT_STEP_TITLE,
                    style: bold
                }),
                new Field({
                    name: "contact",
                    separator: "\n\n",
                    defaultValue: DEFAULT_OPPORTUNITY_CONTACT,
                    style: normal
                }),
                new Field({ name: "comments", style: smaller, canBeEmpty: true }),
            ]
        });
        this.loadFromSheet();
        if (stepData) {
            this.updateStepData(stepData);
        }
    }
    Step.isEmpty = function (what) {
        return Object.keys(what).length === 0;
    };
    Step.prototype.asJson = function (additionalData) {
        if (additionalData === void 0) { additionalData = {}; }
        return __assign(__assign({}, this.stepData.asJson()), additionalData);
    };
    Step.prototype.getFieldValue = function (name) {
        return this.stepData.getFieldValue(name);
    };
    Step.prototype.loadFromSheet = function () {
        if (this.isNew || cellIsEmpty(this.row, this.col)) {
            return;
        }
        var cell = this.sh.getRange(this.row, this.col);
        this.stepData.loadFromSheet(cell);
    };
    Object.defineProperty(Step.prototype, "state", {
        get: function () {
            return this.stepData.state;
        },
        set: function (name) {
            this.stepData.state = name;
        },
        enumerable: false,
        configurable: true
    });
    Step.prototype.reset = function (_a) {
        var sh = _a.sh, row = _a.row, col = _a.col;
        this.sh = sh;
        this.row = row;
        this.col = col;
    };
    Step.prototype.updateColors = function (cell) {
        if (!cell) {
            cell = this.sh.getRange(this.row, this.col);
        }
        var state = getApp().stateFromName(this.state);
        if (!state)
            return;
        cell.setBackground(state.bg);
        cell.setFontColor(state.fg);
    };
    Step.prototype.updateFields = function (fieldsData) {
        if (fieldsData === void 0) { fieldsData = {}; }
        this.stepData.updateValues(fieldsData);
    };
    Step.prototype.updateStepData = function (initData) {
        if (!initData)
            return;
        this.validateStepData(initData);
        var state = initData.state, stepData = __rest(initData, ["state"]);
        if (state) {
            this.state = state;
        }
        this.stepData.updateValues(stepData);
    };
    Step.prototype.updateUI = function () {
        var dataCell = this.sh.getRange(this.row, this.col);
        this.stepData.updateCell(dataCell);
        this.updateColors(dataCell);
        this.isNew = false;
    };
    Step.prototype.validateStepData = function (stepData) {
        validDate(stepData.date, "Date");
        if (stepData.time === ":") {
            stepData.time = "";
        }
        validTime(stepData.time);
    };
    return Step;
}());
