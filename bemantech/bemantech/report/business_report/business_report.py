# Copyright (c) 2026, Tariqul Islam and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, add_months, getdate


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	if not filters:
		filters = {}
	
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Particulars"),
			"fieldname": "particulars",
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 150,
		},
	]


def get_data(filters: dict) -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
	company = filters.get("company")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	
	# Initialize data structure
	data = []
	
	# 1. Cash Sales (Sales Invoice paid in cash within date range)
	cash_sales = get_cash_sales(company, from_date, to_date)
	data.append(["Cash Sales", cash_sales])
	
	# 2. Down Payment (custom_down_payment from Sales Invoice)
	down_payment = get_down_payment(company, from_date, to_date)
	data.append(["Down Payment", down_payment])
	
	# 3. Installment Recovery (Payment received for installments)
	installment_recovery = get_installment_recovery(company, from_date, to_date)
	data.append(["Installment Recovery", installment_recovery])
	
	# 4. Cash in Hand Last Month
	last_month_date = add_months(getdate(from_date), -1)
	cash_in_hand_last_month = get_cash_in_hand(company, last_month_date)
	data.append(["Cash in Hand (Last Month)", cash_in_hand_last_month])
	
	# 5. Total Cash
	total_cash = cash_sales + down_payment + installment_recovery + cash_in_hand_last_month
	data.append(["Total Cash", total_cash])
	
	# 6. Net Cash in Hand (current)
	net_cash_in_hand = get_cash_in_hand(company, to_date)
	data.append(["Net Cash in Hand", net_cash_in_hand])
	
	# 7. Total Sales Price (Total sales within date range)
	total_sales_price = get_total_sales(company, from_date, to_date)
	data.append(["Total Sales Price", total_sales_price])
	
	# 8. Current Sales Due (Outstanding from customers)
	current_sales_due = get_customer_outstanding(company, to_date)
	data.append(["Current Sales Due (Customer Due)", current_sales_due])
	
	# 9. Current Month Recovery (Payments received from customers in current period)
	current_month_recovery = get_payments_received(company, from_date, to_date)
	data.append(["Current Month Recovery", current_month_recovery])
	
	# 10. Total Due (select date range)
	total_due = get_total_outstanding(company, from_date, to_date)
	data.append(["Total Due (Date Range)", total_due])
	
	# 11. Inventory Purchases
	inventory_purchases = get_inventory_purchases(company, from_date, to_date)
	data.append(["Inventory Purchases", inventory_purchases])
	
	return data


def get_cash_sales(company, from_date, to_date):
	"""Get cash sales from Sales Invoice where payment is received in cash."""
	result = frappe.db.sql("""
		SELECT SUM(si.grand_total)
		FROM `tabSales Invoice` si
		WHERE si.company = %(company)s
			AND si.docstatus = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND si.outstanding_amount = 0
			AND si.is_return = 0
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_down_payment(company, from_date, to_date):
	"""Get total down payment from Sales Invoice custom field."""
	result = frappe.db.sql("""
		SELECT SUM(si.custom_down_payment)
		FROM `tabSales Invoice` si
		WHERE si.company = %(company)s
			AND si.docstatus = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND si.is_return = 0
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_installment_recovery(company, from_date, to_date):
	"""Get installment payments received."""
	result = frappe.db.sql("""
		SELECT SUM(pe.paid_amount)
		FROM `tabPayment Entry` pe
		WHERE pe.company = %(company)s
			AND pe.docstatus = 1
			AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND pe.payment_type = 'Receive'
			AND pe.party_type = 'Customer'
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_cash_in_hand(company, as_of_date):
	"""Get cash in hand from cash accounts using GL Entry."""
	result = frappe.db.sql("""
		SELECT SUM(gle.debit - gle.credit)
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON gle.account = acc.name
		WHERE gle.company = %(company)s
			AND acc.account_type = 'Cash'
			AND gle.posting_date <= %(as_of_date)s
			AND gle.is_cancelled = 0
	""", {"company": company, "as_of_date": as_of_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_total_sales(company, from_date, to_date):
	"""Get total sales amount from Sales Invoice."""
	result = frappe.db.sql("""
		SELECT SUM(si.grand_total)
		FROM `tabSales Invoice` si
		WHERE si.company = %(company)s
			AND si.docstatus = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND si.is_return = 0
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_customer_outstanding(company, as_of_date):
	"""Get total outstanding from customers."""
	result = frappe.db.sql("""
		SELECT SUM(outstanding_amount)
		FROM `tabSales Invoice`
		WHERE company = %(company)s
			AND docstatus = 1
			AND posting_date <= %(as_of_date)s
			AND outstanding_amount > 0
			AND is_return = 0
	""", {"company": company, "as_of_date": as_of_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_payments_received(company, from_date, to_date):
	"""Get total payments received from customers."""
	result = frappe.db.sql("""
		SELECT SUM(pe.paid_amount)
		FROM `tabPayment Entry` pe
		WHERE pe.company = %(company)s
			AND pe.docstatus = 1
			AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND pe.payment_type = 'Receive'
			AND pe.party_type = 'Customer'
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_total_outstanding(company, from_date, to_date):
	"""Get total outstanding dues within date range."""
	result = frappe.db.sql("""
		SELECT SUM(outstanding_amount)
		FROM `tabSales Invoice`
		WHERE company = %(company)s
			AND docstatus = 1
			AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND outstanding_amount > 0
			AND is_return = 0
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_inventory_purchases(company, from_date, to_date):
	"""Get inventory purchases from Purchase Invoice."""
	result = frappe.db.sql("""
		SELECT SUM(pi.grand_total)
		FROM `tabPurchase Invoice` pi
		WHERE pi.company = %(company)s
			AND pi.docstatus = 1
			AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND pi.is_return = 0
			AND pi.update_stock = 1
	""", {"company": company, "from_date": from_date, "to_date": to_date})
	
	return flt(result[0][0]) if result and result[0][0] else 0.0
