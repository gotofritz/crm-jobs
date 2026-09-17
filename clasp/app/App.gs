// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
/**
 * You can't instantiate global objects and keep them around in GAS,
 * as they get destroyed between user actions. You can't use
 * PropertyService because it only accepts strings as value. The only
 * solution is to re-create it for every call. This function does so
 * lazily
 */
// eslint-disable-next-line @typescript-eslint/naming-convention
var app_;
var getApp = function () {
    if (!app_) {
        app_ = new App();
    }
    return app_;
};
var App = /** @class */ (function () {
    function App() {
    }
    Object.defineProperty(App.prototype, "states", {
        get: function () {
            if (!this.states_) {
                this.states_ = new StatesManager();
                this.loadStates();
            }
            return this.states_;
        },
        enumerable: false,
        configurable: true
    });
    App.prototype.loadStates = function () {
        var sh = SS.getActiveSheet();
        var range = sh.getRange(DATA_ROW_HEADER, DATA_COL_STATES_START, 1, sh.getLastColumn() - DATA_COL_STATES_START + 1);
        this.states_.loadStates(range);
    };
    App.prototype.statesAsListOfNames = function () {
        return this.states.asListOfNames();
    };
    App.prototype.stateFromColor = function (colorName) {
        return this.states.fromColor(colorName);
    };
    App.prototype.stateFromName = function (stateName) {
        return this.states.fromName(stateName);
    };
    return App;
}());
