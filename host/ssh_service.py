import paramiko


def create_ssh_client(ip: str, port: int, username: str, password: str):
    """Open SSH only for the scheduled root-password rotation task."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=ip,
            port=port,
            username=username,
            password=password,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )
        return client
    except Exception:
        client.close()
        raise
