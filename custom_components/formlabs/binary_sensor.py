from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FormlabsCoordinator


def _printer_status(printer: dict[str, Any]) -> dict[str, Any]:
    ps = printer.get("printer_status")
    return ps if isinstance(ps, dict) else {}


def _status(printer: dict[str, Any]) -> str | None:
    val = _printer_status(printer).get("status")
    return str(val) if val is not None else None


def _safe_get_name(printer: dict[str, Any]) -> str:
    return (
        printer.get("alias")
        or printer.get("name")
        or printer.get("printer_name")
        or printer.get("serial")
        or "Formlabs printer"
    )


def _ready_to_print_bool(printer: dict[str, Any]) -> bool | None:
    """
    Formlabs payload examples:
      ready_to_print: READY_TO_PRINT_READY
      ready_to_print: READY_TO_PRINT_NOT_READY
    Some models may use simple booleans or different strings.
    """
    val = _printer_status(printer).get("ready_to_print")
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).upper()
    if "NOT_READY" in s:
        return False
    if s.endswith("_READY") or "READY" == s:
        return True
    return None


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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FormlabsCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    printers = coordinator.data.get("printers_by_serial", {})
    entities: list[BinarySensorEntity] = []

    for serial in printers.keys():
        entities.extend(
            [
                FormlabsOnlineBinarySensor(coordinator, serial),
                FormlabsPrintingBinarySensor(coordinator, serial),
                FormlabsPausedBinarySensor(coordinator, serial),
                FormlabsErrorBinarySensor(coordinator, serial),
                FormlabsWaitingForResolutionBinarySensor(coordinator, serial),
                FormlabsReadyToPrintBinarySensor(coordinator, serial),
            ]
        )

    async_add_entities(entities)


class FormlabsOnlineBinarySensor(_Base, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_online"
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool:
        # "Online" = we have a status and it isn't explicitly OFFLINE
        s = _status(self._printer())
        if s is None:
            return False
        return str(s).upper() not in ("OFFLINE", "DISCONNECTED", "UNKNOWN")


class FormlabsPrintingBinarySensor(_Base, BinarySensorEntity):
    _attr_icon = "mdi:printer-3d-nozzle"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_printing"
        self._attr_name = "Printing"

    @property
    def is_on(self) -> bool:
        return str(_status(self._printer()) or "").upper() == "PRINTING"


class FormlabsPausedBinarySensor(_Base, BinarySensorEntity):
    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_paused"
        self._attr_name = "Paused"

    @property
    def is_on(self) -> bool:
        return str(_status(self._printer()) or "").upper() == "PAUSED"


class FormlabsErrorBinarySensor(_Base, BinarySensorEntity):
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_error"
        self._attr_name = "Error"

    @property
    def is_on(self) -> bool:
        s = str(_status(self._printer()) or "").upper()
        # Formlabs sometimes uses statuses like CHECK_PRINTER
        return s in ("ERROR", "CHECK_PRINTER", "FAILED", "FAILURE", "ATTENTION")


class FormlabsWaitingForResolutionBinarySensor(_Base, BinarySensorEntity):
    _attr_icon = "mdi:account-alert"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_waiting_for_resolution"
        self._attr_name = "Waiting for resolution"

    @property
    def is_on(self) -> bool:
        s = str(_status(self._printer()) or "").upper()
        # Conservative detection: any "RESOLUTION" keyword or explicit state
        return s == "WAITING_FOR_RESOLUTION" or "RESOLUTION" in s


class FormlabsReadyToPrintBinarySensor(_Base, BinarySensorEntity):
    _attr_icon = "mdi:check-decagram"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_ready_to_print"
        self._attr_name = "Ready to print"

    @property
    def is_on(self) -> bool:
        v = _ready_to_print_bool(self._printer())
        return bool(v) if v is not None else False
