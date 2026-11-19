import secrets
import re
import string

from celery import shared_task
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .encryption import encrypt_password
from .models import Host, HostCountStatistic, HostCredential, HostPasswordRotationLog
from .encryption import decrypt_password
from .ssh_service import create_ssh_client


@shared_task
def rotate_root_passwords():
    """Rotate configured root credentials and retain encrypted audit copies."""
    rotated, errors = 0, []
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    for host in Host.objects.iterator():
        try:
            credential = HostCredential.objects.filter(host=host).first()
            if credential is None:
                raise ValueError("未配置主机凭据")
            if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", credential.username):
                raise ValueError("凭据用户名格式不安全，已跳过")

            original_ciphertext = credential.encrypted_password
            old_password = decrypt_password(original_ciphertext)
            password = "".join(secrets.choice(alphabet) for _ in range(32))
            client = create_ssh_client(host.ip, host.port, credential.username, old_password)
            try:
                stdin, stdout, stderr = client.exec_command("chpasswd", timeout=30)
                stdin.write(f"{credential.username}:{password}\n")
                stdin.flush()
                if stdout.channel.recv_exit_status() != 0:
                    raise RuntimeError(stderr.read().decode("utf-8", errors="replace")[:255] or "远程修改密码失败")
            finally:
                client.close()

            encrypted = encrypt_password(password)
            with transaction.atomic():
                updated = HostCredential.objects.filter(
                    pk=credential.pk, encrypted_password=original_ciphertext
                ).update(encrypted_password=encrypted, updated_time=timezone.now())
                if not updated:
                    raise RuntimeError("凭据在轮换期间被修改，需人工核对新密码")
                HostPasswordRotationLog.objects.create(
                    host=host, username=credential.username, encrypted_password=encrypted
                )
            rotated += 1
        except Exception as exc:
            errors.append({"host_id": host.id, "error": str(exc)[:255]})
    return {"rotated": rotated, "errors": errors}


@shared_task
def record_daily_host_counts():
    today = timezone.localdate()
    from idc.models import IDC
    rows = list(IDC.objects.select_related("city").annotate(host_count=Count("hosts")))
    with transaction.atomic():
        for row in rows:
            HostCountStatistic.objects.update_or_create(
                statistic_date=today, idc=row,
                defaults={"city": row.city, "host_count": row.host_count},
            )
    return {"date": today.isoformat(), "idcs_recorded": len(rows)}
