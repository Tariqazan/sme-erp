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

        // On a new form, fetch the customer's outstanding balance from the API
        if (frm.is_new()) {
            set_outstanding_before(frm);
        }
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

        // Refresh the outstanding balance for a new entry when the party changes
        if (frm.is_new()) {
            set_outstanding_before(frm);
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

// Fetch the customer's outstanding balance (before this payment) from the API
function set_outstanding_before(frm) {
    if (frm.doc.party_type !== "Customer" || !frm.doc.party) {
        return;
    }

    frappe.call({
        method: "erpnext.accounts.utils.get_balance_on",
        args: {
            party_type: "Customer",
            party: frm.doc.party,
            company: frm.doc.company,
            date: frm.doc.posting_date,
        },
        callback: function (r) {
            if (r && r.message !== undefined && r.message !== null) {
                frm.set_value("custom_total_outstanding_before", flt(r.message));
            }
        },
    });
}
