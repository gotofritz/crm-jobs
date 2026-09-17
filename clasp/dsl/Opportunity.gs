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
var Opportunity = /** @class */ (function () {
    function Opportunity(_a) {
        var _b = _a === void 0 ? {} : _a, _c = _b.sh, sh = _c === void 0 ? SS.getActiveSheet() : _c, _d = _b.row, row = _d === void 0 ? DATA_ROW_START : _d, metadata = _b.metadata, _e = _b.isNew, isNew = _e === void 0 ? false : _e;
        this.row = DATA_ROW_START;
        this.steps = [];
        this.sh = sh;
        this.row = row;
        this.steps = [];
        this.isNew = isNew;
        this.metadataHead = new StateToSheetBridge({
            fields: [
                new Field({
                    name: "company",
                    separator: " / ",
                    defaultValue: "????",
                    style: bold
                }),
                new Field({
                    name: "position",
                    separator: "\n\n",
                    defaultValue: "[TBC]",
                    style: bold
                }),
                new Field({ name: "comments", style: smaller, canBeEmpty: true }),
            ],
            colBg: COL_BG_META,
            colFg: COL_FG_META
        });
        this.metadataBody = new StateToSheetBridge({
            fields: [
                new Field({
                    name: "date",
                    separator: "\n\n",
                    defaultValue: asString(new Date()),
                    style: bold
                }),
                new Field({
                    name: "source",
                    separator: "\n",
                    defaultValue: DEFAULT_OPPORTUNITY_SOURCE,
                    style: bold
                }),
                new Field({
                    name: "contact",
                    defaultValue: DEFAULT_OPPORTUNITY_CONTACT,
                    style: normal
                }),
            ],
            colBg: COL_BG_META,
            colFg: COL_FG_META
        });
        this.loadFromSheet();
        if (metadata) {
            this.updateMetadata(metadata);
        }
    }
    Opportunity.asStepIndex = function (col) {
        return col - DATA_COL_LATEST;
    };
    Opportunity.asColIndex = function (opportunityIndex) {
        return opportunityIndex + DATA_COL_LATEST;
    };
    Opportunity.isValid = function (row) {
        return !cellIsEmpty(row, DATA_COL_METAHEAD);
    };
    Opportunity.prototype.asJson = function (additionalData) {
        if (additionalData === void 0) { additionalData = {}; }
        return __assign(__assign(__assign({}, this.metadataHead.asJson()), this.metadataBody.asJson()), additionalData);
    };
    Opportunity.prototype.createStep = function (data) {
        var newStep = new Step({
            sh: this.sh,
            stepData: data,
            row: this.row,
            isNew: true
        });
        this.steps.unshift(newStep);
        this.sortSteps();
    };
    Opportunity.prototype.deleteStep = function (id) {
        if (id === void 0) { id = -1; }
        if (!(id in this.steps)) {
            msgAndDie("There isn't a step ".concat(id));
        }
        this.steps.splice(id, 1);
    };
    Opportunity.prototype.getFieldValue = function (name) {
        var value = this.metadataHead.getFieldValue(name);
        return value === null ? this.metadataBody.getFieldValue(name) : value;
    };
    /**
     * getLastColumn() returns the last column with data anywhere on the sheet.
     * This returns the last column with data on this row
     */
    Opportunity.prototype.getLastColumnForOpportunity = function () {
        var startCol = DATA_COL_LATEST;
        var howMany = this.sh.getLastColumn() - startCol + 1;
        var stepCells = this.sh
            .getRange(this.row, startCol, 1, howMany)
            .getValues()[0];
        /* NOTE: you can't use stepCells.entries(), it gets transpiled
           to non working JS! Namely
           for (var _i = 0, _a = stepCells.entries(); _i < _a.length; _i++) {
              var _b = _a[_i], i = _b[0], col = _b[1];
              ...
              stepCells.entries() is an iterator, so _a[_i] doesn't do anything
        */
        var i = stepCells.length;
        while (--i >= 0) {
            if (!valueIsEmpty(stepCells[i])) {
                return startCol + i;
            }
        }
        return startCol - 1;
    };
    Opportunity.prototype.loadFromSheet = function () {
        if (this.isNew || cellIsEmpty(this.row, DATA_COL_METAHEAD)) {
            return;
        }
        this.metadataHead.loadFromSheet(this.sh.getRange(this.row, DATA_COL_METAHEAD));
        this.metadataBody.loadFromSheet(this.sh.getRange(this.row, DATA_COL_METABODY));
        var startCol = DATA_COL_LATEST;
        var endCol = this.getLastColumnForOpportunity();
        this.steps = this.steps.filter(function (item) { return item.isNew; });
        for (var i = startCol; i <= endCol; i += 1) {
            var newStep = new Step({ sh: this.sh, row: this.row, col: i });
            this.steps.push(newStep);
        }
    };
    Opportunity.prototype.reindex = function () {
        for (var i = 0; i < this.steps.length; i += 1) {
            this.steps[i].reset({
                sh: this.sh,
                row: this.row,
                col: Opportunity.asColIndex(i)
            });
        }
    };
    Opportunity.prototype.reset = function (_a) {
        var sh = _a.sh, row = _a.row;
        this.sh = sh;
        this.row = row;
    };
    Opportunity.prototype.sortSteps = function () {
        this.steps.sort(function (a, b) {
            var _a;
            var sortedByGroup = getApp().states.sortByGroup(a.state, b.state);
            if (sortedByGroup !== 0) {
                return sortedByGroup;
            }
            var aDate = new Date("".concat(a.getFieldValue("date"), " ").concat(a.getFieldValue("time")));
            var bDate = new Date("".concat(b.getFieldValue("date"), " ").concat(b.getFieldValue("time")));
            if (((_a = getApp().stateFromName(a.state)) === null || _a === void 0 ? void 0 : _a.group) === "COMPLETE") {
                return aDate < bDate ? 1 : -1;
            }
            return aDate < bDate ? -1 : 1;
        });
        return this;
    };
    Opportunity.prototype.updateFieldsInStep = function (data, id) {
        if (id === void 0) { id = -1; }
        if (!(id in this.steps)) {
            msgAndDie("There isn't a step ".concat(id));
        }
        this.steps[id].updateFields(data);
    };
    Opportunity.prototype.updateFields = function (fieldsData) {
        this.metadataHead.updateValues(fieldsData);
        this.metadataBody.updateValues(fieldsData);
    };
    Opportunity.prototype.updateMetadata = function (metadata) {
        this.validateMetadata(metadata);
        this.metadataHead.updateValues(metadata);
        this.metadataBody.updateValues(metadata);
        if (metadata.steps) {
            this.steps = metadata.steps.slice();
        }
    };
    Opportunity.prototype.updateStep = function (stepData, id) {
        if (id === void 0) { id = -1; }
        if (!(id in this.steps)) {
            msgAndDie("There isn't a step ".concat(id));
        }
        this.steps[id] = new Step({
            sh: this.sh,
            row: this.row,
            col: Opportunity.asColIndex(stepData.id),
            stepData: stepData
        });
        this.sortSteps();
    };
    Opportunity.prototype.updateUI = function () {
        this.reindex();
        var startCol = DATA_COL_METAHEAD;
        var metadataCell = this.sh.getRange(this.row, startCol);
        this.metadataHead.updateCell(metadataCell);
        metadataCell = this.sh.getRange(this.row, startCol + 1);
        this.metadataBody.updateCell(metadataCell);
        startCol = DATA_COL_LATEST;
        var numCols = this.sh.getLastColumn() - DATA_COL_LATEST;
        this.sh
            .getRange(this.row, startCol, 1, numCols)
            .deleteCells(SpreadsheetApp.Dimension.COLUMNS);
        for (var _i = 0, _a = this.steps; _i < _a.length; _i++) {
            var step = _a[_i];
            step.updateUI();
        }
        this.isNew = false;
        return this;
    };
    Opportunity.prototype.validateMetadata = function (metadata) {
        validDate(metadata.date, "Date");
    };
    return Opportunity;
}());
