from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FormlabsCoordinator


# ----------------------------
# Helpers
# ----------------------------
def _printer_status(printer: dict[str, Any]) -> dict[str, Any]:
    ps = printer.get("printer_status")
    return ps if isinstance(ps, dict) else {}


def _printer_status_str(printer: dict[str, Any]) -> str | None:
    val = _printer_status(printer).get("status")
    return str(val) if val is not None else None


def _current_print_run(printer: dict[str, Any]) -> dict[str, Any] | None:
    cpr = _printer_status(printer).get("current_print_run")
    return cpr if isinstance(cpr, dict) else None


def _safe_get_name(printer: dict[str, Any]) -> str:
    return (
        printer.get("alias")
        or printer.get("name")
        or printer.get("printer_name")
        or printer.get("serial")
        or "Formlabs printer"
    )


def _to_dt(val: Any):
    if not val:
        return None
    if hasattr(val, "tzinfo"):
        return dt_util.as_utc(val)
    if isinstance(val, str):
        dt = dt_util.parse_datetime(val)
        return dt_util.as_utc(dt) if dt else None
    return None


def _format_hms(total_seconds: int | float | None) -> str | None:
    if total_seconds is None:
        return None
    try:
        s = int(float(total_seconds))
    except (TypeError, ValueError):
        return None
    if s < 0:
        s = 0
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _format_hms_from_ms(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    try:
        sec = float(ms) / 1000.0
    except (TypeError, ValueError):
        return None
    return _format_hms(sec)


# -------- Tank helpers --------
def _tank_status(printer: dict[str, Any]) -> dict[str, Any] | None:
    ts = printer.get("tank_status")
    return ts if isinstance(ts, dict) else None


def _tank_obj(printer: dict[str, Any]) -> dict[str, Any] | None:
    ts = _tank_status(printer)
    if not ts:
        return None
    tank = ts.get("tank")
    return tank if isinstance(tank, dict) else None


def _tank_material(printer: dict[str, Any]) -> str | None:
    tank = _tank_obj(printer)
    if not tank:
        return None
    val = tank.get("material") or tank.get("material_name") or tank.get("display_name")
    return str(val) if val is not None else None


def _tank_print_time_ms(printer: dict[str, Any]) -> int | None:
    tank = _tank_obj(printer)
    if not tank:
        return None
    val = tank.get("print_time_ms")
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _tank_layers_printed(printer: dict[str, Any]) -> int | None:
    tank = _tank_obj(printer)
    if not tank:
        return None
    val = tank.get("layers_printed")
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# -------- Cartridge helpers (Form 4 dict / Form 3/3L list) --------
def _cartridge_status_item(printer: dict[str, Any]) -> dict[str, Any] | None:
    cs = printer.get("cartridge_status")

    # Form 4: dict
    if isinstance(cs, dict):
        return cs

    # Form 3/3L: list
    if isinstance(cs, list):
        for item in cs:
            if isinstance(item, dict) and isinstance(item.get("cartridge"), dict):
                return item

    return None


def _cartridge_obj(printer: dict[str, Any]) -> dict[str, Any] | None:
    item = _cartridge_status_item(printer)
    if not item:
        return None
    cart = item.get("cartridge")
    return cart if isinstance(cart, dict) else None


def _cartridge_material(printer: dict[str, Any]) -> str | None:
    cart = _cartridge_obj(printer)
    if not cart:
        return None
    code = cart.get("material")
    return str(code) if code is not None else None


def _cartridge_remaining_ml(printer: dict[str, Any]) -> float | None:
    cart = _cartridge_obj(printer)
    if not cart:
        return None
    init_v = cart.get("initial_volume_ml")
    disp_v = cart.get("volume_dispensed_ml")
    try:
        if init_v is None or disp_v is None:
            return None
        remaining = float(init_v) - float(disp_v)
        if remaining < 0:
            remaining = 0.0
        return remaining
    except (TypeError, ValueError):
        return None


_SENSITIVE_SUBSTRINGS = ("token", "secret", "password", "authorization", "cookie")


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(s in lk for s in _SENSITIVE_SUBSTRINGS):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


# ----------------------------
# Setup
# ----------------------------
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FormlabsCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    printers = coordinator.data.get("printers_by_serial", {})
    entities: list[SensorEntity] = []

    for serial in printers.keys():
        entities.extend(
            [
                # Core
                FormlabsPrinterStatusSensor(coordinator, serial),
                FormlabsFirmwareSensor(coordinator, serial),
                FormlabsLastPingSensor(coordinator, serial),

                # Current job (available only when a print run exists)
                FormlabsCurrentJobNameSensor(coordinator, serial),
                FormlabsCurrentJobStatusSensor(coordinator, serial),
                FormlabsProgressPercentSensor(coordinator, serial),
                FormlabsTimeRemainingSensor(coordinator, serial),
                FormlabsTimeRemainingHmsSensor(coordinator, serial),
                FormlabsElapsedTimeSensor(coordinator, serial),
                FormlabsElapsedTimeHmsSensor(coordinator, serial),
                FormlabsCurrentLayerSensor(coordinator, serial),
                FormlabsLayerCountSensor(coordinator, serial),
                FormlabsMaterialNameSensor(coordinator, serial),

                # Consumables (Capteurs)
                FormlabsCartridgeMaterialSensor(coordinator, serial),
                FormlabsCartridgeRemainingMlSensor(coordinator, serial),
                FormlabsTankMaterialSensor(coordinator, serial),
                FormlabsTankPrintTimeHmsSensor(coordinator, serial),

                # Consumables (Diagnostic)
                FormlabsTankPrintTimeMsSensor(coordinator, serial),
                FormlabsTankLayersPrintedSensor(coordinator, serial),

                # Diagnostic raw payload (keep!)
                FormlabsRawPayloadSensor(coordinator, serial),
            ]
        )

    async_add_entities(entities)


# ----------------------------
# Base
# ----------------------------
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


class _PrintRunBase(_Base):
    def _run(self) -> dict[str, Any] | None:
        return _current_print_run(self._printer())

    @property
    def available(self) -> bool:
        return super().available and self._run() is not None


# ----------------------------
# Core sensors
# ----------------------------
class FormlabsPrinterStatusSensor(_Base, SensorEntity):
    _attr_icon = "mdi:printer-3d"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_printer_status"
        self._attr_name = "Printer status"

    @property
    def native_value(self):
        return _printer_status_str(self._printer())


class FormlabsFirmwareSensor(_Base, SensorEntity):
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_firmware_version"
        self._attr_name = "Firmware version"

    @property
    def native_value(self):
        p = self._printer()
        return p.get("firmware_version") or p.get("firmware")


class FormlabsLastPingSensor(_Base, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_last_ping"
        self._attr_name = "Last ping"

    @property
    def native_value(self):
        p = self._printer()
        ps = _printer_status(p)
        return _to_dt(ps.get("last_pinged_at") or p.get("last_pinged_at"))


# ----------------------------
# Current job sensors
# ----------------------------
class FormlabsCurrentJobNameSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:briefcase-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_current_job_name"
        self._attr_name = "Current job name"

    @property
    def native_value(self):
        run = self._run() or {}
        return run.get("name")


class FormlabsCurrentJobStatusSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_current_job_status"
        self._attr_name = "Current job status"

    @property
    def native_value(self):
        run = self._run() or {}
        status = run.get("status")
        return str(status) if status is not None else None


class FormlabsProgressPercentSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:progress-check"
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_progress_percent"
        self._attr_name = "Progress"

    @property
    def native_value(self):
        run = self._run() or {}
        try:
            layer = run.get("currently_printing_layer")
            total = run.get("layer_count")
            if layer is None or total in (None, 0):
                return None
            layer_f = float(layer)
            total_f = float(total)
            if total_f <= 0:
                return None
            pct = (layer_f / total_f) * 100.0
            if pct < 0:
                pct = 0
            if pct > 100:
                pct = 100
            return round(pct)
        except (TypeError, ValueError):
            return None


class FormlabsTimeRemainingSensor(_PrintRunBase, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_time_remaining"
        self._attr_name = "Time remaining"

    @property
    def native_value(self):
        run = self._run() or {}
        ms = run.get("estimated_time_remaining_ms")
        try:
            if ms is None:
                return None
            return int(float(ms) / 1000.0)
        except (TypeError, ValueError):
            return None


class FormlabsTimeRemainingHmsSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_time_remaining_hms"
        self._attr_name = "Time remaining (HMS)"

    @property
    def native_value(self):
        run = self._run() or {}
        ms = run.get("estimated_time_remaining_ms")
        try:
            if ms is None:
                return None
            seconds = float(ms) / 1000.0
        except (TypeError, ValueError):
            return None
        return _format_hms(seconds)


class FormlabsElapsedTimeSensor(_PrintRunBase, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_elapsed_time"
        self._attr_name = "Elapsed time"

    @property
    def native_value(self):
        run = self._run() or {}
        ms = run.get("elapsed_duration_ms")
        try:
            if ms is None:
                return None
            return int(float(ms) / 1000.0)
        except (TypeError, ValueError):
            return None


class FormlabsElapsedTimeHmsSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_elapsed_time_hms"
        self._attr_name = "Elapsed time (HMS)"

    @property
    def native_value(self):
        run = self._run() or {}
        ms = run.get("elapsed_duration_ms")
        try:
            if ms is None:
                return None
            seconds = float(ms) / 1000.0
        except (TypeError, ValueError):
            return None
        return _format_hms(seconds)


class FormlabsCurrentLayerSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:layers-triple"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_current_layer"
        self._attr_name = "Current layer"

    @property
    def native_value(self):
        run = self._run() or {}
        val = run.get("currently_printing_layer")
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None


class FormlabsLayerCountSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:layers-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_layer_count"
        self._attr_name = "Layer count"

    @property
    def native_value(self):
        run = self._run() or {}
        val = run.get("layer_count")
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None


class FormlabsMaterialNameSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:flask-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_material_name"
        self._attr_name = "Material"

    @property
    def native_value(self):
        run = self._run() or {}
        return run.get("material_name") or run.get("material")


# ----------------------------
# Consumables (Capteurs)
# ----------------------------
class FormlabsCartridgeMaterialSensor(_Base, SensorEntity):
    _attr_icon = "mdi:cartridge"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_cartridge_material"
        self._attr_name = "Cartridge material"

    @property
    def native_value(self):
        return _cartridge_material(self._printer())


class FormlabsCartridgeRemainingMlSensor(_Base, SensorEntity):
    _attr_icon = "mdi:water-percent"
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_cartridge_volume_remaining_ml"
        self._attr_name = "Cartridge volume remaining"

    @property
    def native_value(self):
        return _cartridge_remaining_ml(self._printer())


class FormlabsTankMaterialSensor(_Base, SensorEntity):
    _attr_icon = "mdi:cup"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_material"
        self._attr_name = "Tank material"

    @property
    def native_value(self):
        return _tank_material(self._printer())


class FormlabsTankPrintTimeHmsSensor(_Base, SensorEntity):
    _attr_icon = "mdi:timer-cog-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_print_time_hms"
        self._attr_name = "Tank print time (HMS)"

    @property
    def native_value(self):
        return _format_hms_from_ms(_tank_print_time_ms(self._printer()))


# ----------------------------
# Consumables (Diagnostic)
# ----------------------------
class FormlabsTankPrintTimeMsSensor(_Base, SensorEntity):
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_unit_of_measurement = "ms"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_print_time_ms"
        self._attr_name = "Tank print time (ms)"

    @property
    def native_value(self):
        return _tank_print_time_ms(self._printer())


class FormlabsTankLayersPrintedSensor(_Base, SensorEntity):
    _attr_icon = "mdi:layers"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_layers_printed"
        self._attr_name = "Tank layers printed"

    @property
    def native_value(self):
        return _tank_layers_printed(self._printer())


# ----------------------------
# Diagnostic "Raw payload" sensor (keep!)
# ----------------------------
class FormlabsRawPayloadSensor(_Base, SensorEntity):
    _attr_icon = "mdi:bug-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_raw_payload"
        self._attr_name = "Raw payload"

    @property
    def native_value(self):
        return _printer_status_str(self._printer()) or "unknown"

    @property
    def extra_state_attributes(self):
        p = self._printer()
        attrs = {
            "serial": p.get("serial"),
            "alias": p.get("alias"),
            "machine_type_id": p.get("machine_type_id"),
            "firmware_version": p.get("firmware_version") or p.get("firmware"),
            "printer_status": p.get("printer_status"),
            "tank_status": p.get("tank_status"),
            "cartridge_status": p.get("cartridge_status"),
        }
        return _redact(attrs)
