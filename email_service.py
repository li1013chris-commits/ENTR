"""Email service for ENTR with multi-language support."""

import os
import logging
from datetime import datetime
from flask_mailman import Mail, EmailMessage

log = logging.getLogger(__name__)
mail = Mail()

TRANSLATIONS = {
    "en": {
        "email.subject.welcome": "Welcome to ENTR",
        "email.subject.verify": "Verify your ENTR account",
        "email.subject.reset": "Reset your ENTR password",
        "email.subject.app_received": "New application received",
        "email.subject.app_status": "Application status changed",
        "email.subject.interview": "Interview scheduled",
        "email.subject.verify_complete": "Verification complete",
        "email.subject.account_deleted": "Account deleted",
        "email.footer.privacy": "Privacy Policy",
        "email.footer.terms": "Terms of Service",
        "email.footer.text": "This email was sent to",
    },
    "es": {
        "email.subject.welcome": "Bienvenido a ENTR",
        "email.subject.verify": "Verifica tu cuenta de ENTR",
        "email.subject.reset": "Restablecer tu contrasena de ENTR",
        "email.subject.app_received": "Nueva solicitud recibida",
        "email.subject.app_status": "Estado de solicitud cambio",
        "email.subject.interview": "Entrevista programada",
        "email.subject.verify_complete": "Verificacion completa",
        "email.subject.account_deleted": "Cuenta eliminada",
        "email.footer.privacy": "Politica de Privacidad",
        "email.footer.terms": "Terminos de Servicio",
        "email.footer.text": "Este email fue enviado a",
    },
    "zh": {
        "email.subject.welcome": "欢迎来到 ENTR",
        "email.subject.verify": "验证您的 ENTR 账户",
        "email.subject.reset": "重置您的 ENTR 密码",
        "email.subject.app_received": "收到新申请",
        "email.subject.app_status": "申请状态已更改",
        "email.subject.interview": "面试已安排",
        "email.subject.verify_complete": "验证完成",
        "email.subject.account_deleted": "账户已删除",
        "email.footer.privacy": "隐私政策",
        "email.footer.terms": "服务条款",
        "email.footer.text": "此邮件已发送至",
    },
    "fr": {
        "email.subject.welcome": "Bienvenue sur ENTR",
        "email.subject.verify": "Verifiez votre compte ENTR",
        "email.subject.reset": "Reinitialiser votre mot de passe ENTR",
        "email.subject.app_received": "Nouvelle candidature recue",
        "email.subject.app_status": "Statut de candidature modifie",
        "email.subject.interview": "Entretien programme",
        "email.subject.verify_complete": "Verification terminee",
        "email.subject.account_deleted": "Compte supprime",
        "email.footer.privacy": "Politique de confidentialite",
        "email.footer.terms": "Conditions d'utilisation",
        "email.footer.text": "Cet email a ete envoye a",
    },
    "pt": {
        "email.subject.welcome": "Bem-vindo ao ENTR",
        "email.subject.verify": "Verifique sua conta ENTR",
        "email.subject.reset": "Redefinir sua senha ENTR",
        "email.subject.app_received": "Nova aplicacao recebida",
        "email.subject.app_status": "Status da aplicacao alterado",
        "email.subject.interview": "Entrevista agendada",
        "email.subject.verify_complete": "Verificacao concluida",
        "email.subject.account_deleted": "Conta deletada",
        "email.footer.privacy": "Politica de Privacidade",
        "email.footer.terms": "Termos de Servico",
        "email.footer.text": "Este email foi enviado para",
    },
    "vi": {
        "email.subject.welcome": "Chao mung den ENTR",
        "email.subject.verify": "Xac minh tai khoan ENTR cua ban",
        "email.subject.reset": "Dat lai mat khau ENTR cua ban",
        "email.subject.app_received": "Da nhan duoc don xin moi",
        "email.subject.app_status": "Trang thai don xin da thay doi",
        "email.subject.interview": "Cuoc phong van da duoc sap lich",
        "email.subject.verify_complete": "Xac minh hoan thanh",
        "email.subject.account_deleted": "Tai khoan da bi xoa",
        "email.footer.privacy": "Chinh sach bao mat",
        "email.footer.terms": "Dieu khoan dich vu",
        "email.footer.text": "Email nay da duoc gui toi",
    },
}


def init_mail(app):
    """Initialize Flask-Mail."""
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "localhost")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@entr.app")
    mail.init_app(app)


def _smtp_configured() -> bool:
    return bool(
        os.environ.get("MAIL_SERVER")
        and os.environ.get("MAIL_USERNAME")
        and os.environ.get("MAIL_PASSWORD")
    )


def _get_email_footer(lang: str = "en") -> str:
    """Get email footer with privacy/terms links."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    footer_text = trans.get("email.footer.text", "This email was sent to")
    privacy = trans.get("email.footer.privacy", "Privacy Policy")
    terms = trans.get("email.footer.terms", "Terms of Service")
    return (
        f"\n\n---\n"
        f"ENTR\n"
        f"{footer_text} {{email}}\n\n"
        f"{privacy} | {terms}"
    )


def _send_mail(to_email: str, subject: str, body: str) -> bool:
    """Send email via SMTP or log to console."""
    if not _smtp_configured():
        log.info(f"SMTP not configured. EMAIL:\nTo: {to_email}\nSubject: {subject}\n\n{body}")
        return False

    try:
        msg = EmailMessage(subject=subject, body=body, to=[to_email])
        msg.send()
        log.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        log.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str, name: str, lang: str = "en") -> bool:
    """Send welcome email on signup."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.welcome", "Welcome to ENTR")
    body = (
        f"Hi {name},\n\n"
        f"Welcome to ENTR. We connect restaurant workers with jobs.\n\n"
        f"Get started by completing your profile.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_verification_email(to_email: str, name: str, token: str, lang: str = "en") -> bool:
    """Send account verification email."""
    frontend_url = os.environ.get("FRONTEND_URL", "https://entr.up.railway.app")
    verify_url = f"{frontend_url}/verify-email?token={token}"

    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.verify", "Verify your ENTR account")
    body = (
        f"Hi {name},\n\n"
        f"Verify your email by clicking this link:\n\n"
        f"{verify_url}\n\n"
        f"Link expires in 24 hours.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_password_reset_email(to_email: str, name: str, token: str, lang: str = "en") -> bool:
    """Send password reset email."""
    frontend_url = os.environ.get("FRONTEND_URL", "https://entr.up.railway.app")
    reset_url = f"{frontend_url}/reset-password?token={token}"

    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.reset", "Reset your ENTR password")
    body = (
        f"Hi {name},\n\n"
        f"Click this link to reset your password:\n\n"
        f"{reset_url}\n\n"
        f"Link expires in 1 hour.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_application_received_email(
    to_email: str,
    employer_name: str,
    worker_name: str,
    job_title: str,
    fit_score: int,
    lang: str = "en",
) -> bool:
    """Send email when new application received."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.app_received", "New application received")
    body = (
        f"Hi {employer_name},\n\n"
        f"{worker_name} applied for {job_title}.\n"
        f"AI match score: {fit_score}/100.\n\n"
        f"Review the application in your dashboard.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_application_status_email(
    to_email: str,
    worker_name: str,
    job_title: str,
    new_status: str,
    lang: str = "en",
) -> bool:
    """Send email when application status changes."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.app_status", "Application status changed")
    body = (
        f"Hi {worker_name},\n\n"
        f"Your application for {job_title} is now {new_status}.\n\n"
        f"Check your dashboard for details.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_interview_proposal_email(
    to_email: str,
    worker_name: str,
    date_time: str,
    restaurant_name: str,
    job_title: str,
    lang: str = "en",
) -> bool:
    """Ask the worker to confirm a proposed interview time."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.interview", "Interview scheduled")
    body = (
        f"Hi {worker_name},\n\n"
        f"{restaurant_name} wants to interview you for {job_title}.\n"
        f"Proposed time: {date_time}\n\n"
        f"Please open your ENTR dashboard to confirm this time.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_interview_scheduled_email(
    to_email: str,
    name: str,
    date_time: str,
    restaurant_name: str,
    job_title: str,
    lang: str = "en",
) -> bool:
    """Send email when interview is scheduled."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.interview", "Interview scheduled")
    body = (
        f"Hi {name},\n\n"
        f"Your interview is scheduled.\n"
        f"Date: {date_time}\n"
        f"Position: {job_title} at {restaurant_name}\n\n"
        f"Check your calendar for meeting details.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_verification_complete_email(
    to_email: str,
    name: str,
    verified: bool,
    lang: str = "en",
) -> bool:
    """Send email when verification completes."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.verify_complete", "Verification complete")
    status = "verified" if verified else "needs resubmission"
    body = (
        f"Hi {name},\n\n"
        f"Your identity verification is {status}.\n\n"
        f"Check your dashboard for details.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)


def send_account_deleted_email(to_email: str, name: str, lang: str = "en") -> bool:
    """Send confirmation email when account is deleted."""
    trans = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    subject = trans.get("email.subject.account_deleted", "Account deleted")
    body = (
        f"Hi {name},\n\n"
        f"Your ENTR account has been deleted.\n"
        f"All your data has been removed.\n\n"
        f"You can create a new account anytime.\n\n"
        f"The ENTR Team"
        + _get_email_footer(lang).format(email=to_email)
    )
    return _send_mail(to_email, subject, body)
