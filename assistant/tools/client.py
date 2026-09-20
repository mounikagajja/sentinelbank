import httpx

from backend.app.core.config import get_settings

settings = get_settings()
TIMEOUT = 15.0


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, token: str, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}/api/v1{path}"
        try:
            response = httpx.request(method, url, headers=self.headers, timeout=TIMEOUT, **kwargs)
        except httpx.RequestError as exc:
            raise ApiError(f"Could not reach the API: {exc}") from exc

        if response.status_code == 404:
            raise ApiError("Not found")
        if response.status_code == 403:
            raise ApiError("This action requires the analyst role")
        if response.status_code == 409:
            raise ApiError(response.json().get("detail", "Conflict"))
        if response.status_code >= 400:
            raise ApiError(f"API returned {response.status_code}: {response.text[:200]}")

        return response.json()

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def patch(self, path: str, json: dict) -> dict:
        return self._request("PATCH", path, json=json)
