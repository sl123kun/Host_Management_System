import platform
import subprocess

def ping_host(ip: str) -> bool:
    """
    检测指定 IP 地址是否能够 Ping 通。
    """

    system = platform.system().lower()

    # 根据操作系统选择 Ping 命令参数
    if system == "windows":
        command = ["ping", "-n", "4", "-w", "1000", ip]

    elif system == "linux":
        command = ["ping", "-c", "4", "-W", "1", ip]

    else:
        raise OSError(f"暂不支持当前操作系统：{system}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=6
        )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        return False

    except FileNotFoundError:
        raise OSError("系统中找不到 ping 命令")

