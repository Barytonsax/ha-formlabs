from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_BASE, TOKEN_URL


class FormlabsAuthError(Exception):
    pass


class FormlabsApiError(Exception):
    pass


class FormlabsApi:
    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str) -> None:
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_type: str = "Bearer"
        self._lock = asyncio.Lock()

    async def async_get_token(self) -> str:
        async with self._lock:
            if self._token:
                return self._token

            data = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }

            async with self._session.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise FormlabsAuthError(f"Token error {resp.status}: {text}")

                payload = await resp.json()

            self._token = payload.get("access_token")
            if not self._token:
                raise FormlabsAuthError(f"Token missing in response: {payload}")

            self._token_type = payload.get("token_type", "Bearer")
            return self._token

    async def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        token = await self.async_get_token()
        headers = {
            "Authorization": f"{self._token_type} {token}",
            "Accept": "application/json",
        }

        url = f"{API_BASE}{path}"
        async with self._session.request(
            method,
            url,
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=25),
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                # reset token on auth errors (safe)
                if resp.status in (401, 403):
                    self._token = None
                raise FormlabsApiError(f"API error {resp.status} on {path}: {text}")
            return await resp.json()

    async def async_list_printers(self) -> list[dict[str, Any]]:
        # ✅ Minimal: only this endpoint for now
        return await self._request("GET", "/printers/")
