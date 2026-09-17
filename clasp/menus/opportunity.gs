// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var createOpportunity = function () {
    var html = HtmlService.createHtmlOutputFromFile("forms/formOpportunity").setTitle("New Opportunity...");
    SpreadsheetApp.getUi().showSidebar(html);
};
var editOpportunity = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var opportunityIndex = Pool.asOpportunityIndex(opportunityRow);
    var myPool = new Pool();
    var opportunityToEdit = myPool.opportunities[opportunityIndex];
    var htmlFragment = asHTMLfragment(opportunityToEdit.asJson({
        id: opportunityIndex
    }));
    var html = HtmlService.createHtmlOutputFromFile(HTML_NAME_OPPORTUNITY)
        .setTitle("Edit Opportunity...")
        .append(htmlFragment);
    SpreadsheetApp.getUi().showSidebar(html);
};
var editCommentsOpportunity = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var opportunityIndex = Pool.asOpportunityIndex(opportunityRow);
    var myPool = new Pool();
    var opportunityToEdit = myPool.opportunities[opportunityIndex];
    var htmlFragment = asHTMLfragment({
        id: opportunityIndex,
        comments: opportunityToEdit.getFieldValue("comments")
    });
    var html = HtmlService.createHtmlOutputFromFile(HTML_NAME_EDIT_COMMENT)
        .append(htmlFragment)
        .setWidth(DIALOG_WIDTH)
        .setHeight(DIALOG_HEIGHT);
    SpreadsheetApp.getUi().showModalDialog(html, "Edit Comment...");
};
var deleteOpportunity = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var ui = SpreadsheetApp.getUi();
    var response = ui.alert("Are you sure you want to delete this opportunity?", ui.ButtonSet.OK_CANCEL);
    if (response === ui.Button.OK) {
        var myPool = new Pool();
        var opportunityIndex = Pool.asOpportunityIndex(opportunityRow);
        myPool.deleteOpportunity(opportunityIndex);
        myPool.updateUI();
    }
};
var sortOpportunities = function () {
    var myPool = new Pool();
    myPool.sortOpportunities().updateUI();
};
