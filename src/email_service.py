import logging
import os
import smtplib
from email.message import EmailMessage

from flask import current_app


LOGGER = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when email delivery fails after SMTP is configured."""


def send_email(recipient: str, subject: str, body_text: str):
    smtp_host = os.getenv('SMTP_HOST', '').strip()
    smtp_port = int(os.getenv('SMTP_PORT', '587').strip() or '587')
    smtp_user = os.getenv('SMTP_USER', '').strip()
    smtp_password = os.getenv('SMTP_PASSWORD', '').strip()
    smtp_use_tls = _get_bool_env('SMTP_USE_TLS', True)
    sender_email = os.getenv('MAIL_FROM_EMAIL', '').strip()
    sender_name = os.getenv('MAIL_FROM_NAME', 'Flowter').strip() or 'Flowter'

    if not smtp_host or not sender_email:
        LOGGER.warning(
            'SMTP nao configurado. Conteudo do e-mail para %s:\nAssunto: %s\n\n%s',
            recipient,
            subject,
            body_text,
        )
        return 'debug'

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = f'{sender_name} <{sender_email}>'
    message['To'] = recipient
    message.set_content(body_text)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            if smtp_use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        LOGGER.exception(
            'Falha ao enviar e-mail para %s usando SMTP %s:%s.',
            recipient,
            smtp_host,
            smtp_port,
        )
        raise EmailDeliveryError(
            'Nao foi possivel enviar o e-mail agora. Revise a configuracao SMTP do Gmail.'
        ) from exc

    return 'sent'


def send_verification_email(user: dict, verification_url: str):
    subject = 'Confirme seu e-mail no Flowter'
    body = (
        f'Ola, {user["nome"]}.\n\n'
        'Confirme seu e-mail para ativar o acesso a sua conta:\n'
        f'{verification_url}\n\n'
        'Se voce nao criou essa conta, ignore esta mensagem.'
    )
    return send_email(user['email'], subject, body)


def send_password_reset_email(user: dict, reset_url: str):
    subject = 'Redefinicao de senha no Flowter'
    body = (
        f'Ola, {user["nome"]}.\n\n'
        'Recebemos uma solicitacao para redefinir sua senha.\n'
        'Use o link abaixo para criar uma nova senha:\n'
        f'{reset_url}\n\n'
        'Se voce nao solicitou essa troca, ignore esta mensagem.'
    )
    return send_email(user['email'], subject, body)


def notify_delivery(channel: str, action_label: str):
    if channel == 'debug':
        current_app.logger.warning(
            '%s gerado sem SMTP configurado. Use o link registrado no log do servidor para testar o fluxo.',
            action_label,
        )


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}
