// Compiled using crm-clasp-2 1.0.0 (TypeScript 4.8.2)
var handleCreateOpportunity = function (data) {
    var myPool = new Pool();
    if (data.id) {
        myPool.updateOpportunity(data, data.id);
    }
    else {
        myPool.createOpportunity(data);
    }
    myPool.updateUI();
};
var handleEditComment = function (data) {
    if (!data.id)
        return;
    var weAreEditingAStep = "row" in data;
    if (weAreEditingAStep) {
        var opportunity = new Opportunity({ row: data.row });
        opportunity.updateFieldsInStep({ comments: data.comments }, 
        // in this case the id represents the Step, i.e. col
        data.id);
        opportunity.updateUI();
    }
    else {
        var myPool = new Pool();
        myPool.updateFieldsInOpportunity({ comments: data.comments }, 
        // in this case the id represents the Opp., i.e. row
        data.id);
        myPool.updateUI();
    }
};
var handleCreateStep = function (data) {
    var opportunity = new Opportunity({ row: data.row });
    if (data.id) {
        opportunity.updateStep(data, data.id);
    }
    else {
        opportunity.createStep(data);
    }
    opportunity.updateUI();
};
