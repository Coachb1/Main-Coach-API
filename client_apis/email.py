"""
api_keys/emails.py

Thin wrapper around your existing send_email_via_email() utility.
Keeps all API-key email logic in one place.
"""
import re

from django.utils.timezone import localtime
from email_sender.helpers import send_email_from_emailit
import logging

logger = logging.getLogger(__name__)

def _is_email(value: str) -> bool:
    return bool(value and re.match(r"[^@]+@[^@]+\.[^@]+", value.strip()))


def send_api_key_creation_email(
    to_email:   str,
    client,                  # ClientUserInfo instance
    key_name:   str,
    raw_key:    str,
    prefix:     str,
    expires_at=None,
    rate_limit: int = 300,
):
    """
    Sends a one-time API key delivery email to `to_email`.

    Called from:
      - ClientAPIKeyAdmin.save_model()   (admin creation)
      - APIKeyListCreateView.post()      (API creation)
    """
    if not _is_email(to_email):
        logger.error(f"Invalid email address: {to_email}")
        return
    
    expiry_line = (
        f"Expires at : {localtime(expires_at).strftime('%d %b %Y, %H:%M %Z')}"
        if expires_at
        else "Expires at : Never"
    )

    subject = f"Your API Key for {client.client_name} — {key_name}"
    dashboard_url = "https://yourdashboard.com/client-api/"  # TODO: replace with actual URL
    body = f"""
<!DOCTYPE html>

<html>
<head>
  <meta charset="UTF-8">
  <title>API Key Created</title>
</head>

<body style="margin:0; padding:0; background-color:#f4f6fb; font-family:Arial, sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="padding:20px;">
    <tr>
      <td align="center">

```
    <!-- Container -->
    <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:10px; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.06);">

      <!-- Header / Branding -->
      <tr>
        <td style="background:#0f172a; padding:20px; text-align:center;">
          <h1 style="color:#ffffff; margin:0; font-size:20px;">
            🚀 CB Platform
          </h1>
          <p style="color:#cbd5e1; margin:4px 0 0; font-size:13px;">
            Secure API Access
          </p>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="padding:24px;">

          <h2 style="margin:0 0 10px; color:#111827;">
            🔐 New API Key Created
          </h2>

          <p style="margin:0 0 20px; color:#4b5563; font-size:14px;">
            A new API key has been generated for your account. Please store it securely — this is the only time it will be shown.
          </p>

          <!-- Details Card -->
          <table width="100%" cellpadding="10" cellspacing="0" style="background:#f9fafb; border-radius:8px; font-size:14px;">
            <tr>
              <td style="color:#6b7280;">Client</td>
              <td style="font-weight:bold;">{client.client_name}</td>
            </tr>
            <tr>
              <td style="color:#6b7280;">Key Name</td>
              <td style="font-weight:bold;">{key_name}</td>
            </tr>
            <tr>
              <td style="color:#6b7280;">Key Prefix</td>
              <td><code>{prefix}…</code></td>
            </tr>
            <tr>
              <td style="color:#6b7280;">Rate Limit</td>
              <td>{rate_limit} requests / minute</td>
            </tr>
            <tr>
              <td style="color:#6b7280;">Expiry</td>
              <td>{expiry_line}</td>
            </tr>
          </table>

          <!-- API Key -->
          <div style="margin-top:20px;">
            <p style="margin:0 0 8px; font-weight:bold;">Your API Key</p>

            <div style="background:#111827; color:#10b981; padding:14px; border-radius:6px; font-family:monospace; font-size:13px; word-break:break-all;">
              {raw_key}
            </div>

            <p style="font-size:12px; color:#6b7280; margin-top:6px;">
              Copy and store this key securely. It will not be shown again.
            </p>
          </div>

          <!-- Usage -->
          <div style="margin-top:20px;">
            <p style="margin:0 0 8px; font-weight:bold;">How to use</p>

            <div style="background:#f3f4f6; padding:12px; border-radius:6px; font-family:monospace; font-size:13px;">
```

Authorization: Api-Key {raw_key} </div>

```
            <div style="margin-top:10px; background:#f3f4f6; padding:12px; border-radius:6px; font-family:monospace; font-size:13px;">
```

curl -H "Authorization: Api-Key {raw_key}" https://yourapi.com/api/v1/ </div> </div>

```
          <!-- CTA -->
          <div style="text-align:center; margin-top:24px;">
            <a href="{dashboard_url}" 
               style="display:inline-block; background:#2563eb; color:#ffffff; padding:12px 20px; border-radius:6px; text-decoration:none; font-size:14px; font-weight:bold;">
              Go to Dashboard
            </a>
          </div>

          <!-- Security Warning -->
          <div style="margin-top:24px; background:#fff7ed; border-left:4px solid #f97316; padding:12px; border-radius:6px;">
            <p style="margin:0; font-size:13px; color:#9a3412;">
              <strong>Security Notice:</strong><br>
              Never share this key publicly or commit it to Git repositories.<br>
              If compromised, revoke it immediately from your dashboard.
            </p>
          </div>

        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f9fafb; padding:16px; text-align:center; font-size:12px; color:#6b7280;">
          If you did not request this, contact support immediately.<br><br>
          © 2026 CB Platform. All rights reserved.
        </td>
      </tr>

    </table>

  </td>
</tr>
```

  </table>

</body>
</html>
"""

    send_email_from_emailit(
        receiver_email      = to_email,
        subject = subject,
        body    = body,
    )