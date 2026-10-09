from __future__ import annotations

import subprocess
from pathlib import Path

from src.core import config
from src.core.logging import logger


def ensure_certs() -> None:
    """Generate webhook TLS certificates if paths are configured but missing."""
    cert_path_value = config.WEBHOOK_SSL_CERT
    key_path_value = config.WEBHOOK_SSL_PRIV

    if not cert_path_value or not key_path_value:
        return

    cert_path = Path(cert_path_value).expanduser().resolve()
    key_path = Path(key_path_value).expanduser().resolve()

    if cert_path.exists() and key_path.exists():
        return

    if not config.WEBHOOK_HOST:
        raise ValueError(
            "Cannot generate webhook certificates: WEBHOOK_HOST is not configured."
        )

    key_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    logger.log(
        f"Generating webhook certificates at {cert_path} and {key_path}.",
        to_console=True,
        to_channel=False,
    )

    subprocess.run(
        [
            "openssl",
            "genrsa",
            "-out",
            str(key_path),
            "2048",
        ],
        check=True,
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-new",
            "-x509",
            "-days",
            "3650",
            "-key",
            str(key_path),
            "-out",
            str(cert_path),
            "-subj",
            f"/CN={config.WEBHOOK_HOST}",
        ],
        check=True,
    )


__all__ = ["ensure_certs"]
