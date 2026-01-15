# Formlabs – Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/github/license/Barytonsax/ha-formlabs)](LICENSE)

Unofficial Home Assistant integration for **Formlabs 3D printers**, using the **Formlabs Developer Cloud API (OAuth 2.0)**.

## Features

### Printers & Jobs
- Printer status (IDLE, PRINTING, PAUSED, ERROR, etc.)
- Online / Ready to print / Waiting for resolution
- Current job name & status
- Progress (%)
- Current layer / total layers
- Time remaining / Elapsed time (seconds)
- Display sensors in **HH:MM:SS** (HMS)

### Consumables
- **Tank**
  - Material
  - Total print time (ms + HMS)
  - Layers printed
- **Cartridge**
  - Material code (e.g. `FLGPGR05`)
  - Remaining volume (ml)
  - Empty status

### Diagnostics
- Firmware version
- Last ping
- Raw printer payload (full API data, redacted)

## Supported devices

✅ **All Formlabs machines supported by the Formlabs Developer Cloud API**

Tested with:
- Form 4
- Form 3 / Form 3L

> Note: Some API structures differ between models (e.g. Form 4 single cartridge vs Form 3/3L multiple cartridges).  
> The integration handles these differences automatically.

## Authentication (OAuth 2.0)

Create OAuth credentials in the Formlabs Developer Dashboard:
https://dashboard.formlabs.com/#developer

You need:
- Client ID
- Client Secret

## Installation

### Manual
1. Copy `custom_components/formlabs` into:
   `config/custom_components/formlabs`
2. Restart Home Assistant
3. Settings → Devices & Services → Add Integration → **Formlabs**

### HACS (Custom repository)
1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add: `Barytonsax/ha-formlabs` as **Integration**
3. Download → Restart Home Assistant

## Entity organization

Entities are split between:
- **Capteurs**: day-to-day values (job, progress, consumables, HMS)
- **Diagnostic**: firmware, last ping, raw payload, low-level counters

## Disclaimer

Not affiliated with or endorsed by Formlabs.  
Formlabs® is a registered trademark of Formlabs Inc.
