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
var Pool = /** @class */ (function () {
    function Pool(_a) {
        var _b = _a === void 0 ? {} : _a, _c = _b.sh, sh = _c === void 0 ? SS.getActiveSheet() : _c;
        this.opportunities = [];
        this.sh = sh;
        this.opportunities = [];
        this.loadFromSheet();
    }
    Pool.asOpportunityIndex = function (row) {
        return row - DATA_ROW_START;
    };
    Pool.asRowIndex = function (opportunityIndex) {
        return opportunityIndex + DATA_ROW_START;
    };
    Pool.prototype.loadFromSheet = function () {
        var startRow = DATA_ROW_START;
        var endRow = this.sh.getLastRow();
        this.opportunities = this.opportunities.filter(function (item) { return item.isNew; });
        for (var i = startRow; i <= endRow; i += 1) {
            if (Opportunity.isValid(i)) {
                this.opportunities.push(new Opportunity({ sh: this.sh, row: i }));
            }
        }
    };
    Pool.prototype.reindex = function (sh) {
        if (sh === void 0) { sh = SS.getActiveSheet(); }
        for (var i = 0; i < this.opportunities.length; i += 1) {
            this.opportunities[i].reset({ sh: sh, row: Pool.asRowIndex(i) });
        }
    };
    Pool.prototype.deleteOpportunity = function (id) {
        if (!(id in this.opportunities)) {
            msgAndDie("There isn't an opportunity ".concat(id));
        }
        this.opportunities.splice(id, 1);
    };
    Pool.prototype.createOpportunity = function (data) {
        var newOpportunity = new Opportunity({
            sh: this.sh,
            metadata: __assign(__assign({}, data), { steps: [] }),
            isNew: true
        });
        newOpportunity.createStep({
            date: data.date,
            time: "",
            title: DEFAULT_STEP_TITLE,
            contact: data.contact
        });
        this.opportunities.unshift(newOpportunity);
    };
    Pool.prototype.sortOpportunities = function () {
        this.opportunities.sort(function (a, b) {
            var _a;
            if (a.steps.length === 0) {
                return -1;
            }
            else if (b.steps.length === 0) {
                return 1;
            }
            var aStep = a.steps[0];
            var bStep = b.steps[0];
            var sortedByGroup = getApp().states.sortByGroup(aStep.state, bStep.state);
            if (sortedByGroup !== 0) {
                return sortedByGroup;
            }
            var sortedByPosition = getApp().states.sortByPosition(aStep.state, bStep.state);
            if (sortedByPosition !== 0) {
                return sortedByPosition;
            }
            var aDate = new Date("".concat(aStep.getFieldValue("date"), " ").concat(aStep.getFieldValue("time")));
            var bDate = new Date("".concat(bStep.getFieldValue("date"), " ").concat(bStep.getFieldValue("time")));
            if (((_a = getApp().stateFromName(aStep.state)) === null || _a === void 0 ? void 0 : _a.group) === "COMPLETE") {
                return aDate < bDate ? 1 : -1;
            }
            return aDate < bDate ? -1 : 1;
        });
        this.reindex();
        return this;
    };
    Pool.prototype.updateFieldsInOpportunity = function (data, id) {
        if (id === void 0) { id = -1; }
        if (!(id in this.opportunities)) {
            msgAndDie("There isn't an opportunity ".concat(id));
        }
        this.opportunities[id].updateFields(data);
    };
    Pool.prototype.updateOpportunity = function (data, id) {
        if (id === void 0) { id = -1; }
        if (!(id in this.opportunities)) {
            msgAndDie("There isn't an opportunity ".concat(id));
        }
        this.opportunities[id] = new Opportunity({
            sh: this.sh,
            metadata: data,
            row: Pool.asRowIndex(data.id)
        });
    };
    Pool.prototype.updateUI = function () {
        this.reindex();
        // There must be at least a row there, otherwise GAS will throw:
        // "Exception: Sorry, it is not possible to delete all non-frozen rows"
        var newLength = this.opportunities.length || 1;
        this.sh.insertRowsBefore(DATA_ROW_START, newLength);
        // If cells in the top row had formatting, they would be copied over
        // in the new one. Get rid of them
        this.sh
            .getRange(DATA_ROW_START, DATA_COL_STATES_START, newLength, this.sh.getLastColumn())
            .clearFormat();
        for (var _i = 0, _a = this.opportunities; _i < _a.length; _i++) {
            var opportunity = _a[_i];
            opportunity.updateUI();
        }
        var startRow = DATA_ROW_START + newLength;
        var nRows = this.sh.getMaxRows() - startRow + 1;
        this.sh.deleteRows(startRow, nRows);
        return this;
    };
    return Pool;
}());
