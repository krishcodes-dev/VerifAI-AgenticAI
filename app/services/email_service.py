import smtplib
import logging
import html as html_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.config import get_settings
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    """Enhanced email service with user personalization"""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        self.logo_url = "https://via.placeholder.com/34x34?text=VA"  # Placeholder for now
        self.app_url = "https://verifai.app"
        self.dashboard_url = "https://verifai.app/app"
    
    # ============ EMAIL TEMPLATES ============
    
    async def send_verification_email(
        self, 
        recipient_email: str, 
        user_name: str, 
        verify_link: str,
        timestamp: Optional[str] = None
    ) -> dict:
        """Send email verification link (signup)"""
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        
        subject = "✉️ Verify Your Email - Welcome to VerifAI"
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta content="width=device-width, initial-scale=1.0" />
    <title>VerifAI Email Verification</title>
</head>
<style>
    .email-wrap {{
        max-width: 600px;
        margin: 28px auto;
        background: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid rgba(10, 47, 79, 0.06);
    }}

    .container {{ padding: 22px }}

    .header {{
        background: linear-gradient(135deg, #0A2F4F 0%, #1FA8A8 100%);
        color: #fff;
        padding: 18px 22px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}

    .brand {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}

    .brand img {{
        height: 34px;
        width: auto;
    }}

    .brand-name {{
        font-weight: 700;
        font-size: 16px;
    }}

    .banner {{
        height: 10px;
        border-radius: 4px;
        margin: 18px 0 14px;
        background: linear-gradient(90deg, #1FA8A8, #34C38F);
    }}

    .btn {{
        display: inline-block;
        padding: 12px 24px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        background: #0A2F4F;
        color: #fff;
        margin-top: 16px;
    }}

    .btn:hover {{
        background: #061B3A;
    }}

    .footer {{
        padding: 16px 22px;
        background: #F4F7FA;
        color: #6B7280;
        font-size: 12px;
    }}

    .muted {{ color: #6B7280; font-size: 13px; }}
</style>

<body>
    <table class="email-wrap" cellpadding="0" cellspacing="0">
    <tr><td>
        <div class="header">
            <div class="brand">
                <img src="{self.logo_url}" alt="VerifAI" />
                <div class="brand-name">Welcome</div>
            </div>
            <div style="font-size:12px;opacity:0.85">{timestamp}</div>
        </div>

        <div class="container">
            <span class="banner"></span>

            <p style="margin:6px 0 10px;font-size:15px;color:#0B1A2B;font-weight:600">
                Hi {html_lib.escape(user_name)} 👋,
            </p>
            
            <p class="muted" style="margin:0 0 16px;line-height:1.6">
                Thanks for signing up with VerifAI! We're thrilled to have you on board.
                <br><br>
                To get started, please verify your email address by clicking the button below.
                This helps us keep your account secure.
            </p>

            <a href="{verify_link}" class="btn">Verify Email Address</a>

            <p class="muted" style="margin-top:16px;line-height:1.6">
                Or copy and paste this link in your browser:<br>
                <code style="background:#F4F7FA;padding:8px;border-radius:4px;display:block;margin-top:8px;word-break:break-all;font-size:11px">
                    {verify_link}
                </code>
            </p>

            <p class="muted" style="margin-top:16px;border-top:1px solid #E8ECF1;padding-top:16px">
                This link will expire in 7 days for your security.
            </p>

        </div>

        <div class="footer">
            <strong>Next Steps:</strong><br>
            1️⃣ Verify your email<br>
            2️⃣ Log in to your dashboard<br>
            3️⃣ Set up your fraud detection<br><br>
            Questions? <a href="mailto:{self.settings.SUPPORT_EMAIL}" style="color:#1FA8A8">Contact our team</a>
            <br><br>
            © {datetime.now().year} VerifAI. All rights reserved.
        </div>
    </td></tr>
    </table>
</body>
</html>
"""
        
        return await self._send_email(recipient_email, subject, html_body)
    
    async def send_password_reset_email(
        self,
        recipient_email: str,
        user_name: str,
        reset_link: str,
        timestamp: Optional[str] = None
    ) -> dict:
        """Send password reset link"""
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        
        subject = "Reset Your Password - VerifAI"
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta content="width=device-width, initial-scale=1.0" />
    <title>Password Reset</title>
</head>
<style>
    .email-wrap {{
        max-width: 600px;
        margin: 28px auto;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid rgba(10, 47, 79, 0.06);
    }}
    .container {{ padding: 22px }}
    .header {{
        background: linear-gradient(135deg, #0A2F4F 0%, #1FA8A8 100%);
        color: #fff;
        padding: 18px 22px;
    }}
    .banner {{
        height: 10px;
        border-radius: 4px;
        margin: 18px 0 14px;
        background: #E6A600;
    }}
    .btn {{
        display: inline-block;
        padding: 12px 24px;
        border-radius: 8px;
        background: #0A2F4F;
        color: #fff;
        text-decoration: none;
        font-weight: 600;
        margin-top: 16px;
    }}
    .footer {{
        padding: 16px 22px;
        background: #F4F7FA;
        color: #6B7280;
        font-size: 12px;
    }}
    .muted {{ color: #6B7280; font-size: 13px; }}
    .alert {{
        background: #FEF3CD;
        border-left: 4px solid #E6A600;
        padding: 12px;
        border-radius: 6px;
        margin: 16px 0;
    }}
</style>

<body>
    <table class="email-wrap" cellpadding="0" cellspacing="0">
    <tr><td>
        <div class="header">
            <div style="font-weight:700;font-size:16px">Password Reset Request</div>
            <div style="font-size:12px;opacity:0.85">{timestamp}</div>
        </div>

        <div class="container">
            <span class="banner"></span>

            <p style="margin:6px 0 10px;font-size:15px;color:#0B1A2B;font-weight:600">
                Hi {html_lib.escape(user_name)},
            </p>
            
            <p class="muted" style="margin:0 0 16px">
                We received a request to reset your VerifAI password.
                <br><br>
                Click the button below to create a new password. 
                <strong>This link expires in 1 hour.</strong>
            </p>

            <a href="{reset_link}" class="btn">Reset Password</a>

            <div class="alert">
                ⚠️ If you didn't request this, please ignore this email.
                Your account remains secure.
            </div>

            <p class="muted" style="margin-top:16px">
                Or copy this link:<br>
                <code style="background:#F4F7FA;padding:8px;border-radius:4px;display:block;margin-top:8px;word-break:break-all;font-size:11px">
                    {reset_link}
                </code>
            </p>

        </div>

        <div class="footer">
            <strong>Security Note:</strong> Never share this link with anyone.<br>
            <a href="mailto:{self.settings.SUPPORT_EMAIL}" style="color:#1FA8A8">Report suspicious activity</a>
            <br><br>
            © {datetime.now().year} VerifAI. All rights reserved.
        </div>
    </td></tr>
    </table>
</body>
</html>
"""
        
        return await self._send_email(recipient_email, subject, html_body)
    
    async def send_fraud_alert(
        self, 
        recipient_email: str, 
        user_name: str, 
        amount: float, 
        merchant: str, 
        fraud_score: float, 
        category: str = "UNKNOWN", 
        timestamp: Optional[str] = None, 
        tx_id: str = "N/A"
    ) -> dict:
        """Send professional fraud alert email (ENHANCED)"""
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        
        risk_level = self._get_risk_level(fraud_score)
        fraud_percentage = int(fraud_score * 100)
        
        subject = f"Security Alert: Unusual Transaction Detected - Action Required"
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta content="width=device-width, initial-scale=1.0" />
    <title>VerifAI Security Alert</title>
</head>
<style>
    .email-wrap {{
        max-width: 600px;
        margin: 28px auto;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid rgba(10, 47, 79, 0.06);
    }}

    .container {{ padding: 22px }}

    .header {{
        background: linear-gradient(135deg, #0A2F4F 0%, #1FA8A8 100%);
        color: #fff;
        padding: 18px 22px;
    }}

    .banner {{
        height: 10px;
        border-radius: 4px;
        margin: 18px 0 14px;
        background: #D52C2C;
    }}

    .detail-list {{
        list-style: none;
        padding: 0;
        margin: 0;
        border-top: 1px solid rgba(10, 47, 79, 0.05);
    }}

    .detail-list li {{
        padding: 12px 0;
        border-bottom: 1px solid rgba(10, 47, 79, 0.03);
        display: flex;
        justify-content: space-between;
    }}

    .label {{ color: #444; font-weight: 600; }}
    .value {{ color: #0B1A2B; }}

    .btn {{
        display: inline-block;
        padding: 10px 16px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        margin-right: 8px;
        margin-top: 16px;
    }}

    .btn-primary {{
        background: #0A2F4F;
        color: #fff;
    }}

    .btn-secondary {{
        background: transparent;
        border: 1px solid #0A2F4F;
        color: #0A2F4F;
    }}

    .footer {{
        padding: 16px 22px;
        background: #F4F7FA;
        color: #6B7280;
        font-size: 12px;
    }}

    .muted {{ color: #6B7280; font-size: 13px; }}
    .alert {{ background: #FFF5F5; padding: 12px; border-radius: 6px; }}
</style>

<body>
    <table class="email-wrap" cellpadding="0" cellspacing="0">
    <tr><td>
        <div class="header">
            <div style="font-weight:700;font-size:16px">🚨 Security Alert</div>
            <div style="font-size:12px;opacity:0.85">{timestamp}</div>
        </div>

        <div class="container">
            <span class="banner"></span>

            <p style="margin:6px 0 10px;font-size:15px;color:#0B1A2B;font-weight:600">
                Hi {html_lib.escape(user_name)},
            </p>
            
            <p class="muted" style="margin:0 0 12px">
                We detected an unusual transaction on your account. Here are the details:
            </p>

            <ul class="detail-list">
                <li><span class="label">Amount</span><span class="value">₹{amount:,.2f}</span></li>
                <li><span class="label">Merchant</span><span class="value">{html_lib.escape(merchant)}</span></li>
                <li><span class="label">Category</span><span class="value">{html_lib.escape(category)}</span></li>
                <li><span class="label">Fraud Score</span><span class="value">{fraud_percentage}%</span></li>
                <li><span class="label">Risk Level</span><span class="value">{risk_level}</span></li>
                <li><span class="label">Status</span><span class="value">⛔ BLOCKED</span></li>
                <li><span class="label">Transaction ID</span><span class="value">{tx_id}</span></li>
            </ul>

            <div class="alert" style="margin-top:16px">
                <strong style="color:#D52C2C">🔒 Your account has been temporarily secured.</strong>
                <br>Access is limited for 24 hours as a precautionary measure.
            </div>

            <div style="margin-top:16px">
                <p style="font-weight:600;color:#0B1A2B;margin:0 0 8px">What should you do?</p>
                <ol class="muted" style="margin:0 0 12px 18px">
                    <li>Review the transaction details above</li>
                    <li>Verify if this was authorized by you</li>
                    <li>Take action using the buttons below</li>
                </ol>
            </div>

            <div style="margin-top:16px">
                <a href="{self.dashboard_url}/transactions/{tx_id}" class="btn btn-primary">
                    ✅ Approve Transaction
                </a>
                <a href="{self.dashboard_url}/report?tx_id={tx_id}" class="btn btn-secondary">
                    ❌ Report as Fraud
                </a>
            </div>

            <p class="muted" style="margin-top:16px;border-top:1px solid #E8ECF1;padding-top:16px">
                View full details and manage your account: 
                <a href="{self.dashboard_url}" style="color:#1FA8A8">{self.dashboard_url}</a>
            </p>

        </div>

        <div class="footer">
            <strong>Need Help?</strong><br>
            📞 Call: {self.settings.SUPPORT_PHONE}<br>
            📧 Email: {self.settings.SUPPORT_EMAIL}<br>
            <br>
            © {datetime.now().year} VerifAI. Protecting your transactions.
        </div>
    </td></tr>
    </table>
</body>
</html>
"""
        
        return await self._send_email(recipient_email, subject, html_body)
    
    async def send_transaction_approved(
        self, 
        recipient_email: str, 
        user_name: str, 
        amount: float, 
        merchant: str, 
        timestamp: Optional[str] = None, 
        tx_id: str = "N/A"
    ) -> dict:
        """Send transaction approved email (ENHANCED)"""
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        
        subject = "✅ Transaction Confirmed - Your Payment Succeeded"
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta content="width=device-width, initial-scale=1.0" />
    <title>Transaction Confirmed</title>
</head>
<style>
    .email-wrap {{
        max-width: 600px;
        margin: 28px auto;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid rgba(10, 47, 79, 0.06);
    }}
    .container {{ padding: 22px }}
    .header {{
        background: linear-gradient(135deg, #0A2F4F 0%, #1FA8A8 100%);
        color: #fff;
        padding: 18px 22px;
    }}
    .banner {{
        height: 10px;
        border-radius: 4px;
        margin: 18px 0 14px;
        background: #34C38F;
    }}
    .detail-list {{
        list-style: none;
        padding: 0;
        margin: 0;
        border-top: 1px solid rgba(10, 47, 79, 0.05);
    }}
    .detail-list li {{
        padding: 12px 0;
        border-bottom: 1px solid rgba(10, 47, 79, 0.03);
        display: flex;
        justify-content: space-between;
    }}
    .label {{ color: #444; font-weight: 600; }}
    .value {{ color: #0B1A2B; }}
    .footer {{
        padding: 16px 22px;
        background: #F4F7FA;
        color: #6B7280;
        font-size: 12px;
    }}
    .muted {{ color: #6B7280; font-size: 13px; }}
</style>

<body>
    <table class="email-wrap" cellpadding="0" cellspacing="0">
    <tr><td>
        <div class="header">
            <div style="font-weight:700;font-size:16px">✅ Payment Succeeded</div>
            <div style="font-size:12px;opacity:0.85">{timestamp}</div>
        </div>

        <div class="container">
            <span class="banner"></span>

            <p style="margin:6px 0 10px;font-size:15px;color:#0B1A2B;font-weight:600">
                Hi {html_lib.escape(user_name)},
            </p>
            
            <p class="muted" style="margin:0 0 12px">
                Your transaction has been successfully completed:
            </p>

            <ul class="detail-list">
                <li><span class="label">Amount</span><span class="value">₹{amount:,.2f}</span></li>
                <li><span class="label">Merchant</span><span class="value">{html_lib.escape(merchant)}</span></li>
                <li><span class="label">Date & Time</span><span class="value">{timestamp}</span></li>
                <li><span class="label">Transaction ID</span><span class="value">{tx_id}</span></li>
                <li><span class="label">Status</span><span class="value">✅ Completed</span></li>
            </ul>

            <p class="muted" style="margin-top:16px">
                If you didn't authorize this transaction, 
                <a href="mailto:{self.settings.SUPPORT_EMAIL}" style="color:#1FA8A8">contact support immediately</a>.
            </p>

            <p style="margin-top:16px;font-size:13px">
                <a href="{self.dashboard_url}/transactions/{tx_id}" style="color:#1FA8A8;text-decoration:none">
                    View in Dashboard →
                </a>
            </p>

        </div>

        <div class="footer">
            © {datetime.now().year} VerifAI. Securing every transaction.
        </div>
    </td></tr>
    </table>
</body>
</html>
"""
        
        return await self._send_email(recipient_email, subject, html_body)
    
    async def send_demo_request_email(
        self,
        user_email: str,
        user_role: str,
        user_name: str,
        user_company: str,
        user_requirement: str = None
    ) -> dict:
        """Send demo request email to support team"""
        
        recipient_email = "krishsanghavi09@gmail.com"
        subject = f" New Demo Request from {html_lib.escape(user_company)}"
        timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        LOGO_URL = "https://raw.githubusercontent.com/ethancodes-6969/VerifAI-AgenticAI/main/assets/verifai-logo.png"
        
        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>New Demo Request — VerifAI</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fa;font-family:Arial, Helvetica, sans-serif;color:#0b1a2b;">

  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fa;padding:28px 16px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table role="presentation" class="email-card" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:10px;border:1px solid rgba(10,47,79,0.06);overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0a2f4f 0%,#1fa8a8 100%);padding:18px 22px;color:#ffffff;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="vertical-align:middle;">
                    <!-- Logo placeholder (replace {{LOGO_URL}} with absolute logo url) -->
                    <img src="{LOGO_URL}" alt="VerifAI" width="36" height="36" style="vertical-align:middle;border-radius:6px;display:inline-block;object-fit:contain"/>
                    <span style="display:inline-block;margin-left:12px;vertical-align:middle;font-weight:700;font-size:16px;line-height:1;color:#ffffff;">
                      VerifAI
                      <span style="display:block;font-weight:500;font-size:11px;opacity:0.9;margin-top:2px;">Enterprise Fraud Detection</span>
                    </span>
                  </td>
                  <td align="right" style="vertical-align:middle;font-size:12px;color:rgba(255,255,255,0.9);">
                    {timestamp}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:22px;">
              <!-- Intro -->
              <h2 style="margin:0 0 8px 0;font-size:18px;color:#0b1a2b;font-weight:700;">🎯 New Demo Request</h2>
              <p style="margin:0 0 14px 0;color:#6b7280;font-size:13px;line-height:1.5;">
                A new user requested a personalized VerifAI demo. Details below — action recommended.
              </p>

              <!-- Details box -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;border-radius:8px;border:1px solid rgba(10,47,79,0.04);overflow:hidden;">
                <tr>
                  <td style="padding:12px 14px;background:#ffffff;border-bottom:1px solid rgba(10,47,79,0.03);">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="font-size:13px;color:#444;font-weight:600;padding-bottom:6px;">Name</td>
                        <td style="font-size:13px;color:#0b1a2b;text-align:right;padding-bottom:6px;">{html_lib.escape(user_name)}</td>
                      </tr>
                      <tr>
                        <td style="font-size:13px;color:#444;font-weight:600;padding-bottom:6px;">Company</td>
                        <td style="font-size:13px;color:#0b1a2b;text-align:right;padding-bottom:6px;">{html_lib.escape(user_company)}</td>
                      </tr>
                      <tr>
                        <td style="font-size:13px;color:#444;font-weight:600;padding-bottom:6px;">User Email</td>
                        <td style="font-size:13px;color:#0b1a2b;text-align:right;padding-bottom:6px;">
                          <a href="mailto:{user_email}" style="color:#0a2f4f;text-decoration:none;font-weight:600;">{user_email}</a>
                        </td>
                      </tr>

                      <tr>
                        <td style="font-size:13px;color:#444;font-weight:600;padding-top:8px;">Role</td>
                        <td style="font-size:13px;color:#0b1a2b;text-align:right;padding-top:8px;">{user_role}</td>
                      </tr>
                      
                      <tr>
                        <td style="font-size:13px;color:#444;font-weight:600;padding-top:8px;vertical-align:top;" colspan="2">
                          <div style="margin-top:8px;margin-bottom:4px;">Requirements:</div>
                          <div style="font-weight:400;color:#0b1a2b;background:#f9f9f9;padding:8px;border-radius:4px;font-size:13px;line-height:1.4;">
                            {html_lib.escape(user_requirement) if user_requirement else "No specific requirements provided."}
                          </div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Action button -->
              <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap;">
                <a href="mailto:{user_email}" style="display:inline-block;padding:10px 16px;background:#0a2f4f;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">
                  Contact User
                </a>
              </div>

              <!-- Small note -->
              <p style="margin:16px 0 0 0;color:#6b7280;font-size:12.5px;line-height:1.45;">
                Note: This message was generated automatically by the VerifAI demo request system. Please follow bank/data security protocols when contacting the user.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:14px 22px;background:#f4f7fa;color:#6b7280;font-size:12px;border-top:1px solid rgba(10,47,79,0.04);">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
                <div>VerifAI Internal System Notification</div>
                <div style="text-align:right;">
                </div>
              </div>
            </td>
          </tr>
        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>

</body>
</html>
"""
        
        return await self._send_email(recipient_email, subject, html_body)

    # ============ HELPERS ============
    
    async def _send_email(self, recipient: str, subject: str, html_body: str) -> dict:
        """Send email using async executor"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._send_smtp,
                recipient,
                subject,
                html_body
            )
            return result
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return {"success": False, "error": str(e)}
    
    def _send_smtp(self, recipient: str, subject: str, html_body: str) -> dict:
        """Synchronous SMTP send"""
        try:
            sender_email = self.settings.EMAIL_SENDER
            sender_password = self.settings.EMAIL_PASSWORD
            smtp_server = self.settings.SMTP_SERVER
            smtp_port = self.settings.SMTP_PORT
            
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = sender_email
            message["To"] = recipient
            
            part = MIMEText(html_body, "html")
            message.attach(part)
            
            if smtp_port == 465:
                # SSL connection
                with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, recipient, message.as_string())
            else:
                # TLS connection (e.g. 587)
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, recipient, message.as_string())
            
            self.logger.info(f"✅ Email sent FROM {sender_email} TO {recipient}")
            return {"success": True, "status": "sent"}
        
        except Exception as e:
            self.logger.error(f"SMTP error: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_risk_level(self, fraud_score: float) -> str:
        """Get risk level label from score"""
        if fraud_score >= 0.80:
            return "🔴 CRITICAL"
        elif fraud_score >= 0.50:
            return "🟠 HIGH"
        elif fraud_score >= 0.20:
            return "🟡 MEDIUM"
        else:
            return "🟢 LOW"