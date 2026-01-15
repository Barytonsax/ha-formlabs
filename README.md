# Formlabs – Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/github/license/Barytonsax/ha-formlabs)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Barytonsax/ha-formlabs)](https://github.com/Barytonsax/ha-formlabs/releases)

Unofficial **Home Assistant integration for Formlabs 3D printers**, built on top of the **Formlabs Developer Cloud API (OAuth 2.0)**.

This integration focuses on **clean entity design**, **useful consumable tracking**, and **developer-friendly diagnostics**, while staying aligned with Home Assistant best practices.

---

## ✨ Features

### 🖨️ Printers & Jobs
- Printer status (IDLE, PRINTING, PAUSED, ERROR, etc.)
- Online / Ready to print / Waiting for resolution
- Current job name & status
- Progress (%)
- Current layer / total layers
- Time remaining / Elapsed time (seconds)
- Display sensors in **HH:MM:SS** (HMS)
- **Print volume (mL)** — estimated resin volume for the current print

---

### 🧪 Consumables
- **Tank**
  - Material
  - Total print time (ms + HMS)
  - Layers printed
- **Cartridge**
  - Material code (e.g. `FLGPGR05`)
  - Remaining volume (mL)
  - Empty status

---

### 🖼️ Media
- **Print thumbnail**
  - Exposed as an attribute on the current job sensor (signed URL, expires)
  - Optional **camera proxy entity** to display the thumbnail directly in Lovelace dashboards  
    (handles expiring Formlabs S3 URLs automatically)

---

### 🛠️ Diagnostics
- Firmware version
- Last ping
- Raw printer payload (full API response, sensitive data redacted)

The **Raw payload** sensor is especially useful to:
- understand API differences between printer generations
- debug missing fields
- contribute improvements to the integration

---

## 🖨️ Supported devices

✅ **All Formlabs machines supported by the Formlabs Developer Cloud API**

Tested with:
- Form 4
- Form 3
- Form 3L

> ℹ️ Some API structures differ between models  
> (e.g. Form 4 single cartridge vs Form 3/3L multiple cartridges).  
> These differences are handled transparently by the integration.

---

## 🔐 Authentication (OAuth 2.0)

This integration uses **OAuth 2.0** via the official Formlabs Developer platform.

Create your credentials here:  
https://dashboard.formlabs.com/#developer

You will need:
- **Client ID**
- **Client Secret**

---

## 🚀 Installation

### Manual installation
1. Copy `custom_components/formlabs` into: config/custom_components/formlabs
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **Formlabs**

---

### HACS (Custom repository)
1. Open **HACS → Integrations**
2. Click **⋮ → Custom repositories**
3. Add `Barytonsax/ha-formlabs` as **Integration**
4. Download → Restart Home Assistant

---

## 🧠 Entity organization

Entities are intentionally split for clarity:

- **Capteurs**  
Day-to-day values (job status, progress, print volume, consumables, HMS sensors)

- **Diagnostic**  
Firmware, last ping, raw payload, low-level counters

- **Camera**  
Print thumbnail proxy (optional, for dashboards)

This keeps dashboards clean while still exposing advanced data when needed.

---

## ⚠️ Disclaimer

This project is **not affiliated with or endorsed by Formlabs**.  
Formlabs® is a registered trademark of Formlabs Inc.
