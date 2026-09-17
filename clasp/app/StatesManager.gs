// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var StatesManager = /** @class */ (function () {
    function StatesManager() {
        this.byName = {};
        this.byColor = {};
        this.list = [];
    }
    StatesManager.prototype.fromColor = function (rgbName) {
        return this.byColor[rgbName];
    };
    StatesManager.prototype.fromName = function (stateName) {
        return this.byName[stateName];
    };
    StatesManager.prototype.asListOfNames = function () {
        return this.list.map(function (phs) { return phs.name; });
    };
    StatesManager.prototype.asState = function (maybeState) {
        if (maybeState instanceof State) {
            return maybeState;
        }
        if (typeof maybeState !== "string") {
            return fail(maybeState);
        }
        maybeState = this.fromName(maybeState) || this.fromColor(maybeState) || "";
        if (!maybeState) {
            return fail(maybeState);
        }
        return maybeState;
        function fail(s) {
            throw Error("not a State: ".concat(s, " [type: ").concat(typeof maybeState, "]"));
        }
    };
    /**
     *
     * @param range
     */
    StatesManager.prototype.loadStates = function (range) {
        var lastCell = range.getValues()[0].length;
        var list = [];
        var byColor = {};
        var byName = {};
        for (var order = 1; order <= lastCell; order += 1) {
            var cell = range.getCell(1, order);
            var cellValue = cell.getValue();
            // NOTE: _never_ use instanceof String with GAS...
            if (!cellValue || typeof cellValue !== "string")
                continue;
            // from " a_group   /  a_name " to "a_group", "a_name"
            var _a = cellValue.split("/").map(function (x) { return x.trim(); }), group = _a[0], name = _a[1];
            var bg = getBgColor(cell);
            var fg = getFgColor(cell);
            var state = new State({
                order: order,
                bg: bg,
                fg: fg,
                name: name,
                group: group
            });
            byColor[bg] = byName[name] = state;
            list.push(state);
        }
        this.byColor = byColor;
        this.byName = byName;
        this.list = list.slice();
    };
    StatesManager.prototype.sortByGroup = function (a, b) {
        // TODO: calculate this by position in header row
        var GROUPS_RANKED = new Map([
            ["ATTENTION", 3],
            ["DUE", 2],
            ["COMPLETE", 1],
        ]);
        var aGroupRank = GROUPS_RANKED.get(this.asState(a).group) || -1;
        var bGroupRank = GROUPS_RANKED.get(this.asState(b).group) || -1;
        if (aGroupRank === bGroupRank) {
            return 0;
        }
        if (aGroupRank < bGroupRank) {
            return 1;
        }
        return -1;
    };
    StatesManager.prototype.sortByPosition = function (a, b) {
        var asListOfNames = this.asListOfNames();
        var indexA = asListOfNames.indexOf(this.asState(a).name);
        var indexB = asListOfNames.indexOf(this.asState(b).name);
        // If either or both are not in the list
        if (indexA === -1 || indexB === -1) {
            return 0;
        }
        // If a comes before b
        if (indexA < indexB) {
            return -1;
        }
        // If a comes after b
        if (indexA > indexB) {
            return 1;
        }
        // If both are the same or some other case
        return 0;
    };
    return StatesManager;
}());
