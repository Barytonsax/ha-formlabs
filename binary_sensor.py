from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FormlabsCoordinator

ONLINE_MAX_AGE = timedelta(minutes=10)


def _printer_status(printer: dict[str, Any]) -> dict[str, Any]:
    ps = printer.get("printer_status")
    return ps if isinstance(ps, dict) else {}


def _printer_status_str(printer: dict[str, Any]) -> str:
    return str(_printer_status(printer).get("status") or "").upper()


def _last_ping_dt(printer: dict[str, Any]):
    val = _printer_status(printer).get("last_pinged_at") or printer.get("last_pinged_at")
    if not val:
        return None
    if hasattr(val, "tzinfo"):
        return dt_util.as_utc(val)
    if isinstance(val, str):
        dt = dt_util.parse_datetime(val)
        return dt_util.as_utc(dt) if dt else None
    return None


def _current_print_run(printer: dict[str, Any]) -> dict[str, Any] | None:
    cpr = _printer_status(printer).get("current_print_run")
    return cpr if isinstance(cpr, dict) else None


def _run_status_str(printer: dict[str, Any]) -> str:
    run = _current_print_run(printer) or {}
    return str(run.get("status") or "").upper()


def _ready_to_print_str(printer: dict[str, Any]) -> str:
    return str(_printer_status(printer).get("ready_to_print") or "").upper()


def _safe_get_name(printer: dict[str, Any]) -> str:
    return (
        printer.get("alias")
        or printer.get("name")
        or printer.get("printer_name")
        or printer.get("serial")
        or "Formlabs printer"
    )


def _cartridge_status_item(printer: dict[str, Any]) -> dict[str, Any] | None:
    cs = printer.get("cartridge_status")
    if isinstance(cs, dict):
        return cs
    if isinstance(cs, list):
        for item in cs:
            if isinstance(item, dict) and isinstance(item.get("cartridge"), dict):
                return item
    return None


def _cartridge_is_empty(printer: dict[str, Any]) -> bool | None:
    item = _cartridge_status_item(printer)
    if not item:
        return None
    cart = item.get("cartridge")
    if not isinstance(cart, dict):
        return None
    val = cart.get("is_empty")
    return val if isinstance(val, bool) else None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FormlabsCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    printers = coordinator.data.get("printers_by_serial", {})
    entities: list[BinarySensorEntity] = []

    for serial in printers.keys():
        entities.extend(
            [
                FormlabsOnlineBinary(coordinator, serial),
                FormlabsPrintingBinary(coordinator, serial),
                FormlabsPausedBinary(coordinator, serial),
                FormlabsErrorBinary(coordinator, serial),
                FormlabsWaitingForResolutionBinary(coordinator, serial),
                FormlabsReadyToPrintBinary(coordinator, serial),
                FormlabsCartridgeEmptyBinary(coordinator, serial),
            ]
        )

    async_add_entities(entities)


class _Base(CoordinatorEntity[FormlabsCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator)
        self._serial = serial

    def _printer(self) -> dict[str, Any]:
        return self.coordinator.data.get("printers_by_serial", {}).get(self._serial, {})

    @property
    def device_info(self):
        p = self._printer()
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": _safe_get_name(p),
            "manufacturer": "Formlabs",
            "model": p.get("machine_type_id") or p.get("machine_type") or p.get("printer_type"),
            "sw_version": p.get("firmware_version") or p.get("firmware"),
        }


class FormlabsOnlineBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:lan-connect"
    _attr_name = "Online"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_online"

    @property
    def is_on(self) -> bool:
        dt = _last_ping_dt(self._printer())
        if not dt:
            return False
        return (dt_util.utcnow() - dt) <= ONLINE_MAX_AGE


class FormlabsPrintingBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:printer-3d"
    _attr_name = "Printing"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_printing"

    @property
    def is_on(self) -> bool:
        p = self._printer()
        run = _current_print_run(p)
        if run is not None:
            return _run_status_str(p) == "PRINTING"
        return _printer_status_str(p) == "PRINTING"


class FormlabsPausedBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:pause-circle"
    _attr_name = "Paused"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_paused"

    @property
    def is_on(self) -> bool:
        p = self._printer()
        run = _current_print_run(p)
        if run is not None:
            return _run_status_str(p) == "PAUSED"
        return _printer_status_str(p) == "PAUSED"


class FormlabsErrorBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:alert-circle"
    _attr_name = "Error"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_error"

    @property
    def is_on(self) -> bool:
        p = self._printer()
        run = _current_print_run(p)
        if run is not None:
            return _run_status_str(p) == "ERROR"
        return _printer_status_str(p) == "ERROR"


class FormlabsWaitingForResolutionBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:alert-decagram-outline"
    _attr_name = "Waiting for resolution"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_waiting_for_resolution"

    @property
    def is_on(self) -> bool:
        p = self._printer()
        run = _current_print_run(p)
        if run is not None:
            return _run_status_str(p) == "WAITING_FOR_RESOLUTION"
        return _printer_status_str(p) == "WAITING_FOR_RESOLUTION"


class FormlabsReadyToPrintBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:check-decagram"
    _attr_name = "Ready to print"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_ready_to_print"

    @property
    def is_on(self) -> bool:
        val = _ready_to_print_str(self._printer())
        if not val:
            return False
        if val == "READY":
            return True
        return "READY" in val


class FormlabsCartridgeEmptyBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:cartridge-alert"
    _attr_name = "Cartridge is empty"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_cartridge_is_empty"

    @property
    def is_on(self) -> bool:
        val = _cartridge_is_empty(self._printer())
        # If unknown, default to False (keeps UI calm). If you prefer "unknown", we can mark unavailable instead.
        return bool(val) if val is not None else False
