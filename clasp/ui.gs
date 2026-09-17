// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
/**
 * Shows an alert and dies
 */
var msgAndDie = function (msg) {
    Browser.msgBox(msg);
    throw Error(msg);
};
