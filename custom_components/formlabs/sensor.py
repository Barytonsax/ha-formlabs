from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime, UnitOfVolume, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FormlabsCoordinator


# ----------------------------
# Helpers (printer / status / run)
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


# ----------------------------
# Tank helpers
# ----------------------------
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


# ----------------------------
# Cartridge helpers (Form 4 dict / Form 3/3L list)
# ----------------------------
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


def _cartridge_is_empty(printer: dict[str, Any]) -> bool | None:
    cart = _cartridge_obj(printer)
    if not cart:
        return None
    val = cart.get("is_empty")
    return bool(val) if val is not None else None


# ----------------------------
# Redaction for Raw payload
# ----------------------------
_SENSITIVE_SUBSTRINGS = ("token", "secret", "password", "authorization", "cookie", "signature", "awsaccesskeyid")


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
        # ---- Capteurs (quotidien)
        entities.extend(
            [
                FormlabsPrinterStatusSensor(coordinator, serial),
                FormlabsCurrentJobNameSensor(coordinator, serial),
                FormlabsCurrentJobStatusSensor(coordinator, serial),
                FormlabsProgressPercentSensor(coordinator, serial),
                FormlabsPrintVolumeMlSensor(coordinator, serial),  # ✅ nouveau: volume_ml
                FormlabsCurrentLayerSensor(coordinator, serial),
                FormlabsLayerCountSensor(coordinator, serial),
                FormlabsMaterialNameSensor(coordinator, serial),
                FormlabsTimeRemainingSensor(coordinator, serial),
                FormlabsElapsedTimeSensor(coordinator, serial),
                # HMS display sensors (reco: ne pas casser les numériques)
                FormlabsTimeRemainingHmsSensor(coordinator, serial),
                FormlabsElapsedTimeHmsSensor(coordinator, serial),
                # Consumables
                FormlabsCartridgeMaterialSensor(coordinator, serial),
                FormlabsCartridgeVolumeRemainingSensor(coordinator, serial),
                FormlabsCartridgeIsEmptySensor(coordinator, serial),
                FormlabsTankMaterialSensor(coordinator, serial),
                FormlabsTankLayersPrintedSensor(coordinator, serial),
                FormlabsTankPrintTimeMsSensor(coordinator, serial),
                FormlabsTankPrintTimeHmsSensor(coordinator, serial),
            ]
        )

        # ---- Diagnostic
        entities.extend(
            [
                FormlabsFirmwareVersionSensor(coordinator, serial),
                FormlabsLastPingSensor(coordinator, serial),
                FormlabsRawPayloadSensor(coordinator, serial),
            ]
        )

    async_add_entities(entities)


# ----------------------------
# Base entity
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
            "model": p.get("machine_type") or p.get("printer_type") or p.get("machine_type_id"),
            "sw_version": p.get("firmware_version") or p.get("firmware"),
        }


class _PrintRunBase(_Base):
    def _run(self) -> dict[str, Any] | None:
        return _current_print_run(self._printer())

    @property
    def available(self) -> bool:
        return super().available and self._run() is not None


# ----------------------------
# Capteurs (quotidien)
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


class FormlabsCurrentJobNameSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:briefcase"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_current_job_name"
        self._attr_name = "Current job name"

    @property
    def native_value(self):
        run = self._run() or {}
        return run.get("name")

    @property
    def extra_state_attributes(self):
        """
        Reco: le thumbnail est une URL AWS signée (Expire/Signature),
        donc on l'expose en attribut (pas en sensor dédié).
        """
        run = self._run() or {}
        attrs: dict[str, Any] = {}

        if run.get("guid"):
            attrs["job_guid"] = run.get("guid")

        # Formlabs payload:
        # print_thumbnail: { thumbnail: "<signed url>" }
        pt = run.get("print_thumbnail")
        if isinstance(pt, dict):
            thumb = pt.get("thumbnail")
            if thumb:
                attrs["thumbnail_url"] = thumb

        return attrs


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
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_progress_percent"
        self._attr_name = "Progress"

    @property
    def native_value(self):
        run = self._run() or {}
        val = run.get("progress") or run.get("progress_percent")
        try:
            if val is None:
                return None
            # si API renvoie 0..1 => convertir
            f = float(val)
            if 0.0 <= f <= 1.0:
                f *= 100.0
            return round(f, 1)
        except (TypeError, ValueError):
            return None


class FormlabsPrintVolumeMlSensor(_PrintRunBase, SensorEntity):
    """✅ Printer status -> current_print_run.volume_ml (estimated print volume)."""

    _attr_icon = "mdi:cup-water"
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_print_volume_ml"
        self._attr_name = "Print volume"

    @property
    def native_value(self):
        run = self._run() or {}
        val = run.get("volume_ml")
        try:
            if val is None:
                return None
            return round(float(val), 2)
        except (TypeError, ValueError):
            return None


class FormlabsCurrentLayerSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:layers-outline"

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
    _attr_icon = "mdi:layers-triple"

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
    _attr_icon = "mdi:flask"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_material_name"
        self._attr_name = "Material"

    @property
    def native_value(self):
        run = self._run() or {}
        val = run.get("material") or run.get("material_name")
        return str(val) if val is not None else None


class FormlabsTimeRemainingSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_time_remaining"
        self._attr_name = "Time remaining"

    @property
    def native_value(self):
        run = self._run() or {}
        # API: estimated_time_remaining_ms
        ms = run.get("estimated_time_remaining_ms")
        try:
            if ms is None:
                return None
            sec = int(float(ms) / 1000.0)
            if sec < 0:
                sec = 0
            return sec
        except (TypeError, ValueError):
            return None


class FormlabsElapsedTimeSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_elapsed_time"
        self._attr_name = "Elapsed time"

    @property
    def native_value(self):
        run = self._run() or {}
        # API: elapsed_duration_ms
        ms = run.get("elapsed_duration_ms")
        try:
            if ms is None:
                return None
            sec = int(float(ms) / 1000.0)
            if sec < 0:
                sec = 0
            return sec
        except (TypeError, ValueError):
            return None


# HMS display sensors (text)
class FormlabsTimeRemainingHmsSensor(_PrintRunBase, SensorEntity):
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_time_remaining_hms"
        self._attr_name = "Time remaining (HMS)"

    @property
    def native_value(self):
        # reuse seconds sensor logic
        run = self._run() or {}
        ms = run.get("estimated_time_remaining_ms")
        return _format_hms_from_ms(ms)


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
        return _format_hms_from_ms(ms)


# Cartridge sensors (capteurs)
class FormlabsCartridgeMaterialSensor(_Base, SensorEntity):
    _attr_icon = "mdi:flask-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_cartridge_material"
        self._attr_name = "Cartridge material"

    @property
    def native_value(self):
        return _cartridge_material(self._printer())


class FormlabsCartridgeVolumeRemainingSensor(_Base, SensorEntity):
    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_cartridge_volume_remaining_ml"
        self._attr_name = "Cartridge volume remaining"

    @property
    def native_value(self):
        val = _cartridge_remaining_ml(self._printer())
        return round(val, 1) if val is not None else None


class FormlabsCartridgeIsEmptySensor(_Base, SensorEntity):
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_cartridge_is_empty"
        self._attr_name = "Cartridge is empty"

    @property
    def native_value(self):
        return _cartridge_is_empty(self._printer())


# Tank sensors (capteurs)
class FormlabsTankMaterialSensor(_Base, SensorEntity):
    _attr_icon = "mdi:cup"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_material"
        self._attr_name = "Tank material"

    @property
    def native_value(self):
        return _tank_material(self._printer())


class FormlabsTankLayersPrintedSensor(_Base, SensorEntity):
    _attr_icon = "mdi:layers-triple"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_layers_printed"
        self._attr_name = "Tank layers printed"

    @property
    def native_value(self):
        return _tank_layers_printed(self._printer())


class FormlabsTankPrintTimeMsSensor(_Base, SensorEntity):
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "ms"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_print_time_ms"
        self._attr_name = "Tank print time (ms)"

    @property
    def native_value(self):
        return _tank_print_time_ms(self._printer())


class FormlabsTankPrintTimeHmsSensor(_Base, SensorEntity):
    _attr_icon = "mdi:clock-time-eight-outline"

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_tank_print_time_hms"
        self._attr_name = "Tank print time (HMS)"

    @property
    def native_value(self):
        return _format_hms_from_ms(_tank_print_time_ms(self._printer()))


# ----------------------------
# Diagnostic sensors
# ----------------------------
class FormlabsFirmwareVersionSensor(_Base, SensorEntity):
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
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_last_ping"
        self._attr_name = "Last ping"

    @property
    def native_value(self):
        p = self._printer()
        ps = _printer_status(p)
        return _to_dt(ps.get("last_pinged_at") or ps.get("last_ping") or p.get("last_pinged_at"))


class FormlabsRawPayloadSensor(_Base, SensorEntity):
    _attr_icon = "mdi:code-json"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FormlabsCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_raw_payload"
        self._attr_name = "Raw payload"

    @property
    def native_value(self):
        # state lisible (sans balancer tout le JSON en state)
        return _printer_status_str(self._printer())

    @property
    def extra_state_attributes(self):
        # JSON complet en attribut, redacted
        return {"payload": _redact(self._printer())}
