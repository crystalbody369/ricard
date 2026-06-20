# -*- coding: utf-8 -*-
"""メール送信（パスワード再設定リンク等）。

認証情報は環境変数から読む（HIROさんが Render に設定。コードに鍵は持たない）：
  SMTP_HOST   例: smtp.gmail.com / smtp.resend.com 等
  SMTP_PORT   既定 587（STARTTLS）。465 なら SSL
  SMTP_USER   SMTP ログインユーザー
  SMTP_PASS   SMTP パスワード（Gmailならアプリパスワード）
  MAIL_FROM   差出人（例 ahiro@ahiro.page）。未設定なら SMTP_USER

未設定でもアプリは落ちない（send_email は False を返し、画面で手動連絡へ誘導）。
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


def mail_configured():
    return bool(os.environ.get("SMTP_HOST", "").strip()
                and os.environ.get("SMTP_USER", "").strip()
                and os.environ.get("SMTP_PASS", "").strip())


def mail_from():
    return (os.environ.get("MAIL_FROM", "").strip()
            or os.environ.get("SMTP_USER", "").strip())


def send_email(to, subject, body):
    """1通送る。成功 True / 失敗・未設定 False。例外は投げない。"""
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    if not (host and user and pw and to):
        return False
    try:
        port = int(os.environ.get("SMTP_PORT", "587") or 587)
    except (TypeError, ValueError):
        port = 587
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from()
    msg["To"] = to
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.login(user, pw)
                s.send_message(msg)
        return True
    except Exception:
        return False
