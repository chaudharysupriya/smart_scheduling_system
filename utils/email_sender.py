"""
utils/email_sender.py
Sends booking and cancellation confirmation emails via SMTP/TLS.
All send operations are wrapped in try/except — a failed email must
never prevent a booking from being saved.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _build_smtp_connection(settings: dict):
    """Opens and returns an authenticated SMTP connection using TLS on port 587."""
    host     = settings.get("smtp_host", "smtp.gmail.com")
    port     = int(settings.get("smtp_port", 587))
    sender   = settings.get("sender_email", "")
    password = settings.get("sender_password", "")
    server = smtplib.SMTP(host, port, timeout=10)
    server.ehlo()
    server.starttls()
    server.login(sender, password)
    return server


# ---------------------------------------------------------------------------
# Booking confirmation
# ---------------------------------------------------------------------------

def send_booking_confirmation(
    customer_name: str,
    customer_email: str,
    booking_reference: str,
    appointment_date: str,
    appointment_time: str,
    service_type: str,
    business_name: str,
    business_settings: dict,
) -> bool:
    """
    Sends a booking confirmation email to the customer.
    Returns True on success, False on any failure.
    The booking is already saved before this is called — failure here is non-fatal.
    """
    if not business_settings.get("email_notifications_enabled", True):
        return True

    sender_email = business_settings.get("sender_email", "")
    if not sender_email or not customer_email:
        return False

    subject = f"Booking Confirmed — {booking_reference} — {business_name}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="max-width:600px;margin:30px auto;background:#ffffff;
                    border-radius:10px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.1);">

        <!-- Header -->
        <tr>
          <td style="background:#2E7D32;padding:28px 32px;text-align:center;">
            <h1 style="color:#ffffff;margin:0;font-size:22px;">
              ✅ Your Appointment is Confirmed
            </h1>
            <p style="color:#C8E6C9;margin:6px 0 0 0;font-size:15px;">
              {business_name}
            </p>
          </td>
        </tr>

        <!-- Greeting -->
        <tr>
          <td style="padding:28px 32px 12px 32px;">
            <p style="font-size:16px;color:#333;margin:0;">
              Hi <strong>{customer_name}</strong>,
            </p>
            <p style="font-size:15px;color:#555;margin:10px 0 0 0;">
              Your appointment has been booked successfully. Here are your details:
            </p>
          </td>
        </tr>

        <!-- Details box -->
        <tr>
          <td style="padding:0 32px 20px 32px;">
            <table width="100%" cellpadding="10" cellspacing="0"
                   style="background:#F1F8E9;border-radius:8px;
                          border-left:4px solid #2E7D32;">
              <tr>
                <td style="color:#555;font-size:14px;width:40%;">
                  <strong>Booking Reference</strong>
                </td>
                <td style="color:#1B5E20;font-size:14px;font-family:monospace;
                           font-weight:bold;">
                  {booking_reference}
                </td>
              </tr>
              <tr>
                <td style="color:#555;font-size:14px;">
                  <strong>Date</strong>
                </td>
                <td style="color:#333;font-size:14px;">{appointment_date}</td>
              </tr>
              <tr>
                <td style="color:#555;font-size:14px;">
                  <strong>Time</strong>
                </td>
                <td style="color:#333;font-size:14px;">{appointment_time}</td>
              </tr>
              <tr>
                <td style="color:#555;font-size:14px;">
                  <strong>Service</strong>
                </td>
                <td style="color:#333;font-size:14px;">{service_type}</td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Cancellation info -->
        <tr>
          <td style="padding:0 32px 24px 32px;">
            <p style="font-size:14px;color:#555;margin:0;">
              <strong>Need to cancel?</strong><br>
              Visit the booking page, scroll to the cancellation section,
              and enter your reference number <strong>{booking_reference}</strong>.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F5F5F5;padding:16px 32px;text-align:center;">
            <p style="color:#9E9E9E;font-size:12px;margin:0;">
              {business_name} &nbsp;·&nbsp; This is an automated message.
            </p>
          </td>
        </tr>

      </table>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = customer_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = _build_smtp_connection(business_settings)
        server.sendmail(sender_email, customer_email, msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        logger.error("Booking confirmation email failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Cancellation confirmation
# ---------------------------------------------------------------------------

def send_cancellation_confirmation(
    customer_name: str,
    customer_email: str,
    booking_reference: str,
    appointment_date: str,
    appointment_time: str,
    business_name: str,
    business_settings: dict,
) -> bool:
    """
    Sends a cancellation confirmation email to the customer.
    Returns True on success, False on any failure.
    """
    if not business_settings.get("email_notifications_enabled", True):
        return True

    sender_email = business_settings.get("sender_email", "")
    if not sender_email or not customer_email:
        return False

    subject = f"Booking Cancelled — {booking_reference} — {business_name}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="max-width:600px;margin:30px auto;background:#ffffff;
                    border-radius:10px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.1);">

        <!-- Header -->
        <tr>
          <td style="background:#C62828;padding:28px 32px;text-align:center;">
            <h1 style="color:#ffffff;margin:0;font-size:22px;">
              ❌ Booking Cancelled
            </h1>
            <p style="color:#FFCDD2;margin:6px 0 0 0;font-size:15px;">
              {business_name}
            </p>
          </td>
        </tr>

        <!-- Greeting -->
        <tr>
          <td style="padding:28px 32px 12px 32px;">
            <p style="font-size:16px;color:#333;margin:0;">
              Hi <strong>{customer_name}</strong>,
            </p>
            <p style="font-size:15px;color:#555;margin:10px 0 0 0;">
              Your appointment has been successfully cancelled.
              Here are the details of the cancelled booking:
            </p>
          </td>
        </tr>

        <!-- Details box -->
        <tr>
          <td style="padding:0 32px 20px 32px;">
            <table width="100%" cellpadding="10" cellspacing="0"
                   style="background:#FFF5F5;border-radius:8px;
                          border-left:4px solid #C62828;">
              <tr>
                <td style="color:#555;font-size:14px;width:40%;">
                  <strong>Booking Reference</strong>
                </td>
                <td style="color:#B71C1C;font-size:14px;font-family:monospace;
                           font-weight:bold;">
                  {booking_reference}
                </td>
              </tr>
              <tr>
                <td style="color:#555;font-size:14px;"><strong>Date</strong></td>
                <td style="color:#333;font-size:14px;">{appointment_date}</td>
              </tr>
              <tr>
                <td style="color:#555;font-size:14px;"><strong>Time</strong></td>
                <td style="color:#333;font-size:14px;">{appointment_time}</td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Rebook info -->
        <tr>
          <td style="padding:0 32px 24px 32px;">
            <p style="font-size:14px;color:#555;margin:0;">
              We hope to see you again soon. Visit the booking page to make
              a new appointment at a time that suits you.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F5F5F5;padding:16px 32px;text-align:center;">
            <p style="color:#9E9E9E;font-size:12px;margin:0;">
              {business_name} &nbsp;·&nbsp; This is an automated message.
            </p>
          </td>
        </tr>

      </table>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = customer_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = _build_smtp_connection(business_settings)
        server.sendmail(sender_email, customer_email, msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        logger.error("Cancellation confirmation email failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Test email
# ---------------------------------------------------------------------------

def send_test_email(business_settings: dict) -> tuple:
    """
    Sends a test email to the sender's own address to verify SMTP credentials.
    Returns (success: bool, message: str).
    """
    sender_email = business_settings.get("sender_email", "")
    if not sender_email:
        return False, "No sender email address configured."

    subject  = "✅ Test Email — Appointment Scheduling System"
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;padding:20px;">
      <h2 style="color:#2E7D32;">✅ Email configuration is working!</h2>
      <p>Your SMTP settings are correctly configured.
         Booking confirmation emails will be sent from
         <strong>{sender_email}</strong>.</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = sender_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = _build_smtp_connection(business_settings)
        server.sendmail(sender_email, sender_email, msg.as_string())
        server.quit()
        return True, "Test email sent successfully."
    except Exception as exc:
        return False, str(exc)
