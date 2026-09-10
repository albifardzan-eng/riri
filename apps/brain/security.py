import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from config.settings import settings


@dataclass(frozen=True)
class MT5Identity:
    account_id: str
    terminal_id: str
    instance_id: str

    @property
    def key(self) -> str:
        return f"{self.account_id}:{self.terminal_id}:{self.instance_id}"


def _valid_secret(supplied: str | None, expected: str) -> bool:
    return (
        bool(supplied and expected)
        and len(expected) >= 32
        and hmac.compare_digest(supplied, expected)
    )


async def require_mt5(
    x_riri_api_key: str | None = Header(default=None),
    x_riri_account_id: str | None = Header(default=None),
    x_riri_terminal_id: str | None = Header(default=None),
    x_riri_instance_id: str | None = Header(default=None),
) -> MT5Identity:
    if not _valid_secret(x_riri_api_key, settings.RIRI_MT5_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid MT5 credential")
    if not all((x_riri_account_id, x_riri_terminal_id, x_riri_instance_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing MT5 identity headers")
    return MT5Identity(x_riri_account_id, x_riri_terminal_id, x_riri_instance_id)


async def require_dashboard(
    authorization: str | None = Header(default=None),
) -> None:
    prefix = "Bearer "
    supplied = authorization[len(prefix):] if authorization and authorization.startswith(prefix) else None
    if not _valid_secret(supplied, settings.RIRI_DASHBOARD_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid dashboard credential")
