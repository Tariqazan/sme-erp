frappe.ui.form.on("Payment Entry", {
	refresh: function(frm) {
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
	},

	party: function(frm) {
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

	party_type: function(frm) {
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
