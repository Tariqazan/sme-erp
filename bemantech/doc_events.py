import frappe
from frappe.utils import flt, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.utils import get_balance_on


def sales_invoice_on_submit(doc, method):
	"""
	Create a payment entry for custom_down_payment amount against the Sales Invoice
	This creates a payment entry when the invoice is submitted.
	"""
	try:
		# Check if custom_down_payment field exists and has a value
		if not hasattr(doc, "custom_down_payment") or not doc.custom_down_payment:
			return
		
		# Check if the amount is greater than zero
		down_payment_amount = flt(doc.custom_down_payment)
		if down_payment_amount <= 0:
			return
		
		# Validate that customer and company are set
		if not doc.customer:
			frappe.msgprint("Customer is required to create payment entry", indicator="orange")
			return
		
		if not doc.company:
			frappe.msgprint("Company is required to create payment entry", indicator="orange")
			return
		
		# Get payment entry for the sales invoice
		payment_entry = get_payment_entry(
			dt="Sales Invoice",
			dn=doc.name,
			party_amount=down_payment_amount
		)
		
		# Set additional details
		payment_entry.posting_date = doc.posting_date or nowdate()
		payment_entry.reference_date = doc.posting_date or nowdate()
		payment_entry.remarks = f"Down payment against Sales Invoice {doc.name}"
		payment_entry.reference_no = doc.name
		
		# Update references to allocate the payment against this invoice
		if payment_entry.references:
			for ref in payment_entry.references:
				ref.allocated_amount = down_payment_amount
		
		# Submit the payment entry
		payment_entry.submit()
		
		frappe.msgprint(
			f"Payment Entry {payment_entry.name} created for down payment amount {down_payment_amount}",
			indicator="green"
		)
		
	except Exception as e:
		frappe.log_error(
			message=f"Error creating payment entry for down payment in Sales Invoice {doc.name}: {str(e)}",
			title="Payment Entry Creation Error"
		)
		frappe.msgprint(
			f"Error creating payment entry: {str(e)}",
			indicator="red"
		)


def payment_entry_after_insert(doc, method):
	"""
	Record the customer's outstanding balance before this payment on
	custom_total_outstanding_before, then set custom_total_outstanding to the
	balance remaining after deducting the paid amount.
	"""
	try:
		# Only applicable when the party is a Customer
		if doc.party_type != "Customer" or not doc.party:
			return

		# Balance before this payment (draft entry hasn't posted GL yet)
		outstanding_before = flt(
			get_balance_on(
				party_type="Customer",
				party=doc.party,
				company=doc.company,
				date=doc.posting_date or nowdate(),
			)
		)

		doc.db_set("custom_total_outstanding_before", outstanding_before)
		doc.db_set(
			"custom_total_outstanding",
			outstanding_before - flt(doc.paid_amount),
		)

	except Exception as e:
		frappe.log_error(
			message=f"Error setting outstanding balances for Payment Entry {doc.name}: {str(e)}",
			title="Payment Entry Outstanding Update Error",
		)
