// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var createStep = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var htmlFragment = asHTMLfragment({
        row: opportunityRow,
        time: validTime(),
        allStates: getApp().statesAsListOfNames()
    });
    var html = HtmlService.createHtmlOutputFromFile(HTML_NAME_STEP)
        .setTitle("New step.Step...")
        .append(htmlFragment);
    SpreadsheetApp.getUi().showSidebar(html);
};
var editCommentsStep = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var stepCol = indexOfSelectedCol();
    if (cellIsEmpty(opportunityRow, stepCol)) {
        msgAndDie("Nothing to edit");
    }
    var stepIndex = Opportunity.asStepIndex(stepCol);
    var opportunity = new Opportunity({ row: opportunityRow });
    var stepToEdit = opportunity.steps[stepIndex];
    var htmlFragment = asHTMLfragment({
        id: stepIndex,
        row: opportunityRow,
        comments: stepToEdit.getFieldValue("comments")
    });
    var html = HtmlService.createHtmlOutputFromFile(HTML_NAME_EDIT_COMMENT)
        .append(htmlFragment)
        .setWidth(DIALOG_WIDTH)
        .setHeight(DIALOG_HEIGHT);
    SpreadsheetApp.getUi().showModalDialog(html, "Edit Comment...");
};
var editStep = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var stepCol = indexOfSelectedCol();
    if (cellIsEmpty(opportunityRow, stepCol)) {
        msgAndDie("Nothing to edit");
    }
    var stepIndex = Opportunity.asStepIndex(stepCol);
    var opportunity = new Opportunity({ row: opportunityRow });
    var stepToEdit = opportunity.steps[stepIndex];
    var htmlFragment = asHTMLfragment(stepToEdit.asJson({
        id: stepIndex,
        row: opportunityRow,
        allStates: getApp().statesAsListOfNames()
    }));
    var html = HtmlService.createHtmlOutputFromFile(HTML_NAME_STEP)
        .setTitle("Edit step.Step...")
        .append(htmlFragment);
    SpreadsheetApp.getUi().showSidebar(html);
};
var sortSteps = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var opportunityIndex = Pool.asOpportunityIndex(opportunityRow);
    var myPool = new Pool();
    var opportunityToEdit = myPool.opportunities[opportunityIndex];
    opportunityToEdit.sortSteps();
    myPool.sortOpportunities().updateUI();
};
var deleteStep = function () {
    var opportunityRow = getSelectedRowOrDie("You need to select one of the opportunities, not there");
    var stepCol = indexOfSelectedCol();
    if (cellIsEmpty(opportunityRow, stepCol)) {
        msgAndDie("Nothing to delete");
    }
    var ui = SpreadsheetApp.getUi();
    var response = ui.alert("Are you sure you want to delete this opportunity's step?", ui.ButtonSet.OK_CANCEL);
    if (response === ui.Button.OK) {
        var opportunity = new Opportunity({ row: opportunityRow });
        var stepIndex = Opportunity.asStepIndex(stepCol);
        opportunity.deleteStep(stepIndex);
        opportunity.updateUI();
    }
};
