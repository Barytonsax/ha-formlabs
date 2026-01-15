from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FormlabsApi

import logging

_LOGGER = logging.getLogger(__name__)


class FormlabsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: FormlabsApi) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name="formlabs",
            update_interval=timedelta(seconds=30),
        )
        self._api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            printers = await self._api.async_list_printers()
            by_serial: dict[str, dict[str, Any]] = {}

            for p in printers:
                serial = p.get("serial")
                if not serial:
                    _LOGGER.debug("Skipping printer without serial: keys=%s", list(p.keys()))
                    continue
                by_serial[str(serial)] = p

            return {"printers_by_serial": by_serial}

        except Exception as err:
            raise UpdateFailed(str(err)) from err
