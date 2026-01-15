from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FormlabsCoordinator


def _printer_status(printer: dict[str, Any]) -> dict[str, Any]:
    ps = printer.get("printer_status")
    return ps if isinstance(ps, dict) else {}


def _status_upper(printer: dict[str, Any]) -> str:
    return str(_printer_status(printer).get("status") or "").upper()


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
            "model": p.get("machine_type") or p.get("printer_type") or p.get("machine_type_id"),
            "sw_version": p.get("firmware_version") or p.get("firmware"),
        }


class FormlabsOnlineBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_online"
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool:
        # pragmatique: si on a un status non vide, on considère online
        return _status_upper(self._printer()) != ""


class FormlabsPrintingBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:printer-3d"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_printing"
        self._attr_name = "Printing"

    @property
    def is_on(self) -> bool:
        return _status_upper(self._printer()) == "PRINTING"


class FormlabsPausedBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_paused"
        self._attr_name = "Paused"

    @property
    def is_on(self) -> bool:
        return _status_upper(self._printer()) == "PAUSED"


class FormlabsErrorBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_error"
        self._attr_name = "Error"

    @property
    def is_on(self) -> bool:
        return _status_upper(self._printer()) == "ERROR"


class FormlabsWaitingForResolutionBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:alert-decagram-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_waiting_for_resolution"
        self._attr_name = "Waiting for resolution"

    @property
    def is_on(self) -> bool:
        ps = _printer_status(self._printer())
        val = ps.get("waiting_for_resolution")
        return bool(val) if val is not None else False


class FormlabsReadyToPrintBinary(_Base, BinarySensorEntity):
    _attr_icon = "mdi:check-decagram"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_ready_to_print"
        self._attr_name = "Ready to print"

    @property
    def is_on(self) -> bool:
        ps = _printer_status(self._printer())
        val = ps.get("ready_to_print")
        # Dans tes payloads c'est souvent bool/str selon modèles
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        return str(val).upper() in ("READY", "TRUE", "YES", "ON", "1")
