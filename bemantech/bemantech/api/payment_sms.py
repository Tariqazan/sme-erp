import frappe
import requests


# BulkSMSBD Configuration - Store these in site_config.json for security
BULKSMSBD_API_KEY = "akQDHrnAU9CQvcppkCBV"
BULKSMSBD_SENDER_ID = "8809617611082"
BULKSMSBD_API_URL = "http://bulksmsbd.net/api/smsapi"


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_mobile(mobile_no):
    if not mobile_no:
        return None

    normalized = str(mobile_no).replace(" ", "").replace("-", "")
    if normalized.startswith("+"):
        normalized = normalized[1:]

    if not normalized:
        return None

    if not normalized.startswith("88"):
        normalized = "88" + normalized

    return normalized


def _format_money(amount):
    if amount in (None, ""):
        return None

    return f"{frappe.utils.flt(amount):,.2f}"


def _get_first_available_value(doc, fieldnames):
    for fieldname in fieldnames:
        value = doc.get(fieldname)
        if value not in (None, ""):
            return value

    return None


def _get_customer_mobile(customer_doc):
    candidates = [
        customer_doc.get("mobile_no"),
        customer_doc.get("custom_mobile_number"),
        customer_doc.get("custom_mobile_no"),
        customer_doc.get("phone"),
    ]

    contact_names = frappe.get_all(
        "Dynamic Link",
        filters={
            "link_doctype": "Customer",
            "link_name": customer_doc.name,
            "parenttype": "Contact",
        },
        pluck="parent",
    )

    for contact_name in contact_names:
        contact_doc = frappe.get_doc("Contact", contact_name)
        candidates.extend([
            contact_doc.get("mobile_no"),
            contact_doc.get("phone"),
        ])

        for row in (contact_doc.get("phone_nos") or []):
            candidates.append(row.get("phone"))

    for candidate in candidates:
        normalized = _normalize_mobile(candidate)
        if normalized:
            return normalized

    return None


def get_sms_config():
    """Get SMS configuration from site config or use defaults."""
    return {
        "api_key": frappe.conf.get("bulksmsbd_api_key", BULKSMSBD_API_KEY),
        "sender_id": frappe.conf.get("bulksmsbd_sender_id", BULKSMSBD_SENDER_ID),
        "api_url": frappe.conf.get("bulksmsbd_api_url", BULKSMSBD_API_URL),
        "test_mode": _as_bool(frappe.conf.get("bulksmsbd_test_mode", 0)),
        "test_recipient": frappe.conf.get("bulksmsbd_test_recipient")
    }


def create_sms_log(mobile_no, message, sent_count=0, response_text=None):
    """Persist SMS attempts in ERPNext for both real and test sends."""
    log = frappe.get_doc({
        "doctype": "SMS Log",
        "sent_to": mobile_no,
        "message": message,
        "no_of_requested_sms": 1,
        "requested_numbers": mobile_no,
        "no_of_sent_sms": sent_count,
        "sent_on": frappe.utils.now()
    }).insert(ignore_permissions=True)

    if response_text:
        frappe.logger("payment_sms").info(response_text)

    return log


def send_sms_bulksmsbd(mobile_no, message):
    """
    Send SMS using BulkSMSBD API.

    Args:
        mobile_no: Receiver mobile number (with or without country code)
        message: SMS message content

    Returns:
        dict: API response
    """
    config = get_sms_config()

    mobile_no = _normalize_mobile(mobile_no)
    if not mobile_no:
        frappe.throw("Mobile number is missing or invalid for SMS sending.")

    payload = {
        "api_key": config["api_key"],
        "senderid": config["sender_id"],
        "number": mobile_no,
        "message": message
    }

    if config["test_mode"]:
        logged_mobile_no = config["test_recipient"] or mobile_no
        create_sms_log(
            logged_mobile_no,
            message,
            sent_count=0,
            response_text=f"SMS test mode enabled. Message not sent to provider. Original recipient: {mobile_no}"
        )
        return {
            "status": "test_mode",
            "sent": False,
            "logged": True,
            "original_recipient": mobile_no,
            "test_recipient": logged_mobile_no,
            "message": message,
        }

    try:
        response = requests.post(config["api_url"], data=payload, timeout=30)
        result = response.json() if response.text else {"status": response.status_code}

        create_sms_log(
            mobile_no,
            message,
            sent_count=1 if response.status_code == 200 else 0,
            response_text=f"BulkSMSBD response: {response.text}"
        )

        return result

    except Exception as e:
        frappe.log_error(f"BulkSMSBD API Error: {str(e)}", "SMS API Error")
        raise


def send_payment_received_sms(doc, method):
    """
    Send SMS to customer when Payment Entry is submitted.
    Triggered via doc_events hook on Payment Entry submit.
    """
    # Only send for "Receive" type payments (customer paying us)
    if doc.payment_type != "Receive":
        return

    # Only send if party type is Customer
    if doc.party_type != "Customer":
        return

    try:
        customer_doc = frappe.get_doc("Customer", doc.party)

        mobile_no = _get_customer_mobile(customer_doc)

        if not mobile_no:
            frappe.log_error(
                f"No mobile number found for customer {doc.party}. "
                f"Checked Customer.mobile_no/custom_mobile_no/phone and linked Contact numbers.",
                "Payment SMS Failed"
            )
            return

        # Get company name
        company = doc.company or frappe.defaults.get_user_default("company")

        # Get payment reference (if linked to invoice)
        reference = ""
        if doc.references and len(doc.references) > 0:
            ref_names = [r.reference_name for r in doc.references[:3]]  # Max 3 refs
            reference = f" against {', '.join(ref_names)}"

        # Format amount
        amount = doc.paid_amount
        currency = doc.paid_from_account_currency or "BDT"

        # Compose SMS message
        message = (
            f"Dear {customer_doc.customer_name}, "
            f"Your payment of {currency} {amount:,.2f}{reference} has been received. "
            f"Thank you for your payment. "
            f"- {company}"
        )

        # Send SMS via BulkSMSBD
        send_sms_bulksmsbd(mobile_no, message)

        frappe.msgprint(f"Payment SMS sent to {mobile_no}", alert=True)

    except Exception as e:
        frappe.log_error(
            f"Failed to send payment SMS for {doc.name}: {str(e)}",
            "Payment SMS Error"
        )


def send_sales_invoice_sms(doc, method):
    """
    Send SMS to customer when Sales Invoice is submitted.
    Triggered via doc_events hook on Sales Invoice on_submit.
    """
    try:
        customer_doc = frappe.get_doc("Customer", doc.customer)

        mobile_no = _get_customer_mobile(customer_doc)

        if not mobile_no:
            frappe.log_error(
                f"No mobile number found for customer {doc.customer}. "
                f"Checked Customer.mobile_no/custom_mobile_no/phone and linked Contact numbers.",
                "Sales Invoice SMS Failed"
            )
            return

        company = doc.company or frappe.defaults.get_user_default("company")
        currency = doc.currency or "BDT"
        is_return = bool(doc.is_return)
        document_label = "Credit Note" if is_return else "Invoice"
        action_verb = "has been issued" if is_return else "has been created"
        amended_info = f" against {doc.amended_from}." if is_return and doc.amended_from else "."
        due_date = frappe.utils.formatdate(doc.due_date) if doc.due_date else ""
        due_info = f" Due date: {due_date}." if due_date else ""

        down_payment = doc.get("custom_down_payment")
        installment_amount = doc.get("custom_each_installment_amount")
        installment_qty = doc.get("custom_installment_qty")

        payment_parts = []

        formatted_down_payment = _format_money(down_payment)
        if formatted_down_payment:
            payment_parts.append(f"Down payment: {currency} {formatted_down_payment}")

        if installment_qty not in (None, ""):
            payment_parts.append(f"Installments: {frappe.utils.cint(installment_qty)}")

        formatted_installment_amount = _format_money(installment_amount)
        if formatted_installment_amount:
            payment_parts.append(
                f"Each installment: {currency} {formatted_installment_amount}"
            )

        payment_info = " Payment info: " + ", ".join(payment_parts) + "." if payment_parts else ""

        message = (
            f"Dear {customer_doc.customer_name}, "
            f"{document_label} {doc.name} for {currency} {doc.grand_total:,.2f} {action_verb}{amended_info}"
            f"{payment_info}"
            f"{due_info} "
            f"- {company}"
        )

        send_sms_bulksmsbd(mobile_no, message)

        frappe.msgprint(f"Sales Invoice SMS sent to {mobile_no}", alert=True)

    except Exception as e:
        frappe.log_error(
            f"Failed to send sales invoice SMS for {doc.name}: {str(e)}",
            "Sales Invoice SMS Error"
        )


@frappe.whitelist()
def send_payment_sms_manually(payment_entry_name):
    """
    Manually trigger SMS for a Payment Entry.
    Can be called from a button on the Payment Entry form.
    """
    doc = frappe.get_doc("Payment Entry", payment_entry_name)
    send_payment_received_sms(doc, "on_submit")
    return {"status": "success", "message": "SMS sent successfully"}


@frappe.whitelist()
def get_sms_balance():
    """Check SMS balance from BulkSMSBD."""
    config = get_sms_config()

    if config["test_mode"]:
        return {
            "status": "test_mode",
            "message": "SMS test mode is enabled. No provider balance is required.",
        }

    try:
        response = requests.post(
            "http://bulksmsbd.net/api/getBalanceApi",
            data={"api_key": config["api_key"]},
            timeout=30
        )
        return response.json()
    except Exception as e:
        frappe.log_error(f"Failed to get SMS balance: {str(e)}", "SMS Balance Error")
        return {"error": str(e)}


@frappe.whitelist()
def sms_debug_test_log():
    """Quick no-arg debug helper to verify SMS log creation in current site."""
    result = send_sms_bulksmsbd("01700000000", "SMS debug test from bemantech")
    latest_sms_log = frappe.get_all(
        "SMS Log",
        fields=["name", "sent_to", "creation", "no_of_sent_sms"],
        order_by="creation desc",
        limit=1,
    )
    return {
        "result": result,
        "latest_sms_log": latest_sms_log[0] if latest_sms_log else None,
    }


@frappe.whitelist()
def sms_debug_run_latest_payment_entry():
    """Run SMS flow for latest submitted Receive Payment Entry (Customer)."""
    payment_entry_name = frappe.db.get_value(
        "Payment Entry",
        {
            "docstatus": 1,
            "payment_type": "Receive",
            "party_type": "Customer",
        },
        "name",
        order_by="modified desc",
    )

    if not payment_entry_name:
        return {
            "status": "no_payment_entry",
            "message": "No submitted Receive Payment Entry found for Customer.",
        }

    payment_doc = frappe.get_doc("Payment Entry", payment_entry_name)
    send_payment_received_sms(payment_doc, "debug_manual")

    latest_sms_log = frappe.get_all(
        "SMS Log",
        fields=["name", "sent_to", "creation", "no_of_sent_sms"],
        order_by="creation desc",
        limit=1,
    )
    return {
        "status": "ok",
        "payment_entry": payment_entry_name,
        "latest_sms_log": latest_sms_log[0] if latest_sms_log else None,
    }
