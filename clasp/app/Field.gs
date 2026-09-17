// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var Field = /** @class */ (function () {
    function Field(_a) {
        var _b = _a.name, name = _b === void 0 ? die("A field without a name makes no sense") : _b, _c = _a.separator, separator = _c === void 0 ? "" : _c, _d = _a.defaultValue, defaultValue = _d === void 0 ? "" : _d, _e = _a.value, value = _e === void 0 ? "" : _e, _f = _a.style, style = _f === void 0 ? normal : _f, _g = _a.canBeEmpty, canBeEmpty = _g === void 0 ? false : _g;
        this.separator = "";
        this.defaultValue = "";
        this.style = normal;
        this.canBeEmpty = false;
        this.name = name;
        this.separator = separator;
        this.style = style;
        this.defaultValue = defaultValue;
        this.canBeEmpty = canBeEmpty;
        this.value = canBeEmpty ? value !== null && value !== void 0 ? value : defaultValue : value || defaultValue;
    }
    Field.prototype.updateValue = function (value) {
        if (value === undefined)
            return;
        this.value = this.canBeEmpty
            ? value
            : value || this.value || this.defaultValue;
    };
    return Field;
}());
