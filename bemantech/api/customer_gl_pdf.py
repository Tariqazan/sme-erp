import frappe
from frappe.utils.pdf import get_pdf
from frappe.desk.query_report import run
from frappe.utils import getdate, nowdate


@frappe.whitelist(allow_guest=False)
def download(customer, company, from_date=None, to_date=None):

    # -------------------------------------------------
    # VALIDATION & DATE RANGE
    # -------------------------------------------------
    if not company:
        frappe.throw("Company is mandatory.")

    from_date = from_date or f"{getdate(nowdate()).year}-01-01"
    to_date = to_date or nowdate()

    customer_doc = frappe.get_doc("Customer", customer)

    # -------------------------------------------------
    # ADDRESS & PHONE (FROM customer_primary_address)
    # -------------------------------------------------
    address_html = ""
    phone = ""

    if customer_doc.customer_primary_address:
        address = frappe.get_doc("Address", customer_doc.customer_primary_address)

        parts = [
            address.address_line1,
            address.address_line2,
            address.city,
            address.state,
            address.pincode,
            address.country
        ]
        address_html = "<br>".join([p for p in parts if p])
        phone = address.phone or ""

    # -------------------------------------------------
    # GENERAL LEDGER REPORT (NO GROUPING)
    # -------------------------------------------------
    report = run(
        report_name="General Ledger",
        filters={
            "company": company,
            "party_type": "Customer",
            "party": [customer],
            "from_date": from_date,
            "to_date": to_date,
	    "categorize_by": "Categorize by Voucher (Consolidated)"
        }
    )

    rows = report.get("result", [])

    # -------------------------------------------------
    # OPENING & CLOSING BALANCE
    # -------------------------------------------------
    opening_balance = 0
    closing_balance = 0

    if rows:
        opening_balance = rows[0].get("balance", 0)
        closing_balance = rows[-1].get("balance", 0)

    rows.insert(0, {
        "posting_date": "",
        "voucher_no": "",
        "remarks": "Opening",
        "debit": "",
        "credit": "",
        "balance": opening_balance
    })

    rows.append({
        "posting_date": "",
        "voucher_no": "",
        "remarks": "Closing",
        "debit": "",
        "credit": "",
        "balance": closing_balance
    })

    # -------------------------------------------------
    # FIXED COLUMNS
    # -------------------------------------------------
    columns = [
        {"label": "Date", "fieldname": "posting_date"},
        {"label": "Reference", "fieldname": "voucher_no"},
        {"label": "Remarks", "fieldname": "remarks"},
        {"label": "Debit", "fieldname": "debit"},
        {"label": "Credit", "fieldname": "credit"},
        {"label": "Balance (Dr - Cr)", "fieldname": "balance"},
    ]

    # -------------------------------------------------
    # HTML TEMPLATE
    # -------------------------------------------------
    html = frappe.render_template("""
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; font-size: 10pt; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #333; padding: 4px; }
            th { background-color: #eee; }
            h2 { text-align: center; }
            .info { margin-bottom: 10px; }
            .right { text-align: right; }
            .bold { font-weight: bold; }
        </style>
    </head>
    <body>

        <h2>Statement of Account</h2>

        <div class="info">
            <p><b>Company:</b> {{ company }}</p>
            <p><b>Customer:</b> {{ customer.customer_name }}</p>
            <p><b>Customer ID:</b> {{ customer.custom_customer_id or "" }}</p>
            <p><b>Phone:</b> {{ phone }}</p>
            <p><b>Address:</b><br>{{ address_html | safe }}</p>
            <p><b>From Date:</b> {{ from_date }}</p>
            <p><b>To Date:</b> {{ to_date }}</p>
        </div>

        <table>
            <thead>
                <tr>
                    {% for col in columns %}
                        <th>{{ col.label }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr class="{% if row.remarks in ['Opening','Closing'] %}bold{% endif %}">
                    {% for col in columns %}
                        <td class="{% if col.fieldname in ['debit','credit','balance'] %}right{% endif %}">
                            {{ row.get(col.fieldname, "") }}
                        </td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>

    </body>
    </html>
    """, {
        "customer": customer_doc,
        "phone": phone,
        "address_html": address_html,
        "columns": columns,
        "rows": rows,
        "from_date": from_date,
        "to_date": to_date,
        "company": company
    })

    # -------------------------------------------------
    # PDF GENERATION
    # -------------------------------------------------
    pdf = get_pdf(html, options={"orientation": "Landscape"})

    frappe.local.response.filename = f"{customer}_Statement_of_Account.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"
