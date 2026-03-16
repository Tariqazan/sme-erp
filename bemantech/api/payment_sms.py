import frappe
import requests


# BulkSMSBD Configuration - Store these in site_config.json for security
BULKSMSBD_API_KEY = "akQDHrnAU9CQvcppkCBV"
BULKSMSBD_SENDER_ID = "8809617611082"
BULKSMSBD_API_URL = "http://bulksmsbd.net/api/smsapi"


def get_sms_config():
    """Get SMS configuration from site config or use defaults."""
    return {
        "api_key": frappe.conf.get("bulksmsbd_api_key", BULKSMSBD_API_KEY),
        "sender_id": frappe.conf.get("bulksmsbd_sender_id", BULKSMSBD_SENDER_ID),
        "api_url": frappe.conf.get("bulksmsbd_api_url", BULKSMSBD_API_URL)
    }


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

    # Ensure number has Bangladesh country code
    mobile_no = mobile_no.replace(" ", "").replace("-", "")
    if not mobile_no.startswith("88"):
        mobile_no = "88" + mobile_no

    payload = {
        "api_key": config["api_key"],
        "senderid": config["sender_id"],
        "number": mobile_no,
        "message": message
    }

    try:
        response = requests.post(config["api_url"], data=payload, timeout=30)
        result = response.json() if response.text else {"status": response.status_code}

        # Log the SMS
        frappe.get_doc({
            "doctype": "SMS Log",
            "sent_to": mobile_no,
            "message": message,
            "no_of_requested_sms": 1,
            "requested_numbers": mobile_no,
            "no_of_sent_sms": 1 if response.status_code == 200 else 0,
            "sent_on": frappe.utils.now()
        }).insert(ignore_permissions=True)

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

        # Get customer mobile number
        mobile_no = customer_doc.mobile_no or customer_doc.get("custom_mobile_no")

        if not mobile_no:
            frappe.log_error(
                f"No mobile number found for customer {doc.party}",
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
