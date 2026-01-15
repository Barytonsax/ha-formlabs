from __future__ import annotations

from typing import Any

import aiohttp

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FormlabsCoordinator


def _printer_status(printer: dict[str, Any]) -> dict[str, Any]:
    ps = printer.get("printer_status")
    return ps if isinstance(ps, dict) else {}


def _current_print_run(printer: dict[str, Any]) -> dict[str, Any] | None:
    cpr = _printer_status(printer).get("current_print_run")
    return cpr if isinstance(cpr, dict) else None


def _thumbnail_url(printer: dict[str, Any]) -> str | None:
    run = _current_print_run(printer)
    if not run:
        return None
    pt = run.get("print_thumbnail")
    if isinstance(pt, dict):
        url = pt.get("thumbnail")
        return str(url) if url else None
    return None


def _safe_get_name(printer: dict[str, Any]) -> str:
    return (
        printer.get("alias")
        or printer.get("name")
        or printer.get("printer_name")
        or printer.get("serial")
        or "Formlabs printer"
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FormlabsCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    printers = coordinator.data.get("printers_by_serial", {})

    session = async_get_clientsession(hass)

    entities: list[Camera] = []
    for serial in printers.keys():
        entities.append(FormlabsPrintThumbnailCamera(coordinator, session, serial))

    async_add_entities(entities)


class FormlabsPrintThumbnailCamera(CoordinatorEntity[FormlabsCoordinator], Camera):
    """Camera proxy that serves the current print thumbnail as image bytes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:image"

    def __init__(
        self,
        coordinator: FormlabsCoordinator,
        session: aiohttp.ClientSession,
        serial: str,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)

        self._session = session
        self._serial = serial

        self._attr_unique_id = f"{serial}_print_thumbnail_camera"
        self._attr_name = "Print thumbnail"

    def _printer(self) -> dict[str, Any]:
        return self.coordinator.data.get("printers_by_serial", {}).get(self._serial, {})

    @property
    def available(self) -> bool:
        # Available only while a signed thumbnail URL exists
        return super().available and _thumbnail_url(self._printer()) is not None

    @property
    def device_info(self):
        p = self._printer()
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": _safe_get_name(p),
            "manufacturer": "Formlabs",
            "model": p.get("machine_type") or p.get("printer_type") or p.get("machine_type_id"),
            "sw_version": p.get("firmware_version") or p.get("firmware"),
        }

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """
        Fetch bytes from the signed S3 thumbnail URL and proxy them to Home Assistant.
        Signed URLs expire; when expired, return None until next coordinator refresh.
        """
        url = _thumbnail_url(self._printer())
        if not url:
            return None

        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                return await resp.read()
        except (aiohttp.ClientError, TimeoutError):
            return None
