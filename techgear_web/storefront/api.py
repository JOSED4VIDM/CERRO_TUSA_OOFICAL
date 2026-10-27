import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class StoreAPIError(Exception):
    def __init__(self, message, status_code=503):
        self.status_code = status_code
        super().__init__(message)


def api_request(path, *, method="GET", token=None, data=None):
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{settings.TECHGEAR_API_URL}/api/{path.lstrip('/')}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8")) if response.status != 204 else None
    except HTTPError as exc:
        try:
            details = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            details = {}
        message = details.get("detail", "La solicitud no pudo completarse.") if isinstance(details, dict) else "La solicitud no pudo completarse."
        raise StoreAPIError(message, exc.code) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise StoreAPIError("No fue posible conectar con la tienda. Intenta de nuevo más tarde.") from exc
