frappe.ui.form.on("Payment Entry", {
    refresh: function (frm) {
        // Fetch and set custom_customer_id on form refresh
        if (frm.doc.party_type === "Customer" && frm.doc.party) {
            // Fetch custom_customer_id from Customer doctype
            frappe.db.get_value("Customer", frm.doc.party, "custom_customer_id", (r) => {
                if (r && r.custom_customer_id) {
                    frm.set_value("custom_customer_id", r.custom_customer_id);
                } else {
                    // Clear the field if customer doesn't have custom_customer_id
                    frm.set_value("custom_customer_id", "");
                }
            });
        } else {
            // Clear custom_customer_id if party_type is not Customer or party is empty
            if (frm.doc.party_type !== "Customer" || !frm.doc.party) {
                frm.set_value("custom_customer_id", "");
            }
        }
        
        // Calculate totals from references
        calculate_reference_totals(frm);
    },

    party: function (frm) {
        // Check if party_type is Customer
        if (frm.doc.party_type === "Customer" && frm.doc.party) {
            // Fetch custom_customer_id from Customer doctype
            frappe.db.get_value("Customer", frm.doc.party, "custom_customer_id", (r) => {
                if (r && r.custom_customer_id) {
                    frm.set_value("custom_customer_id", r.custom_customer_id);
                } else {
                    // Clear the field if customer doesn't have custom_customer_id
                    frm.set_value("custom_customer_id", "");
                }
            });
        } else {
            // Clear custom_customer_id if party_type is not Customer or party is empty
            frm.set_value("custom_customer_id", "");
        }
    },

    party_type: function (frm) {
        // Clear custom_customer_id when party_type changes (unless it's Customer with a party)
        if (frm.doc.party_type !== "Customer" || !frm.doc.party) {
            frm.set_value("custom_customer_id", "");
        } else if (frm.doc.party_type === "Customer" && frm.doc.party) {
            // If party_type is Customer and party exists, fetch custom_customer_id
            frappe.db.get_value("Customer", frm.doc.party, "custom_customer_id", (r) => {
                if (r && r.custom_customer_id) {
                    frm.set_value("custom_customer_id", r.custom_customer_id);
                } else {
                    frm.set_value("custom_customer_id", "");
                }
            });
        }
    }
});

// Calculate totals from Payment Entry Reference child table
function calculate_reference_totals(frm) {
    let grand_total = 0;
    let total_outstanding = 0;

    if (frm.doc.references && frm.doc.references.length > 0) {
        frm.doc.references.forEach(function (ref) {
            // Sum up total_amount (Grand Total)
            if (ref.total_amount) {
                grand_total += flt(ref.total_amount);
            }
            // Sum up outstanding_amount (Outstanding)
            if (ref.outstanding_amount) {
                total_outstanding += flt(ref.outstanding_amount);
            }
        });
    }

    // Set the calculated totals in custom fields
    frm.set_value("custom_grand_total", grand_total);
    frm.set_value("custom_total_outstanding", total_outstanding);
}

// Handle Payment Entry Reference child table events
frappe.ui.form.on("Payment Entry Reference", {
    reference_name: function (frm, cdt, cdn) {
        // Recalculate totals when a reference is added/changed
        setTimeout(function () {
            calculate_reference_totals(frm);
        }, 100);
    },

    total_amount: function (frm) {
        // Recalculate when total_amount changes
        calculate_reference_totals(frm);
    },

    outstanding_amount: function (frm) {
        // Recalculate when outstanding_amount changes
        calculate_reference_totals(frm);
    },

    allocated_amount: function (frm) {
        // Recalculate when allocated_amount changes
        calculate_reference_totals(frm);
    },

    references_remove: function (frm) {
        // Recalculate when a reference is removed
        calculate_reference_totals(frm);
    }
});
