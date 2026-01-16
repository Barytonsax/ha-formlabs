# Formlabs – Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/Barytonsax/ha-formlabs)](https://github.com/Barytonsax/ha-formlabs/releases)

Unofficial **Home Assistant integration for Formlabs 3D printers**, built on top of the **Formlabs Developer Cloud API (OAuth 2.0)**.

The goal of this integration is to provide **clean, stable entities**, **useful consumables tracking**, and **developer-friendly diagnostics**, following Home Assistant best practices.

---

## ✨ Highlights

- 🖨️ Printer state & print job monitoring (status, progress, layers, timings)
- 🧪 Consumables tracking (tank + cartridge)
- 🖼️ Print thumbnail (attribute + optional camera entity)
- 🛠️ Diagnostics (firmware, last ping, redacted raw payload)
- ✅ **Stable entities after a print ends**  
  (no more `Unavailable` / `Unknown` just because a job finished)

---

## 🖨️ Features

### Printers & Jobs
- Printer status (IDLE, PRINTING, PAUSED, ERROR, etc.)
- Online / Ready to print / Waiting for resolution
- Current job name & status
- Progress (%)
- Current layer / total layers
- Time remaining / Elapsed time (seconds)
- Display sensors in **HH:MM:SS** (HMS)
- **Print volume (mL)** — estimated resin volume for the current print

### Consumables
- **Tank**
  - Material
  - Total print time (ms + HMS)
  - Layers printed
- **Cartridge**
  - Material code (e.g. `FLGPGR05`)
  - Remaining volume (mL)
  - Empty status

### Media
- **Print thumbnail**
  - Available as an attribute on the current job sensor (signed URL, expires)
  - Optional **camera entity** to display the thumbnail directly in Lovelace dashboards  
    (proxies the signed URL and avoids disappearing images after a print ends)

### Diagnostics
- Firmware version
- Last ping
- Raw printer payload (full API response, sensitive data redacted)

The **Raw payload** diagnostic sensor is especially useful to:
- understand API differences between printer generations
- debug missing or model-specific fields
- contribute improvements to the integration

---

## ✅ Supported devices

✅ **All Formlabs machines supported by the Formlabs Developer Cloud API**

Tested with:
- Form 4
- Form 3
- Form 3L

> ℹ️ Some API structures differ between models  
> (for example Form 4 single cartridge vs Form 3/3L multiple cartridges).  
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

### Option A — HACS (Custom repository)
1. Open **HACS → Integrations**
2. Click **⋮ → Custom repositories**
3. Add `Barytonsax/ha-formlabs` as **Integration**
4. Download → Restart Home Assistant

### Option B — Manual installation
1. Copy `custom_components/formlabs` into:  
   `config/custom_components/formlabs`
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for **Formlabs**

---

## 🧩 Entities & organization

Entities are intentionally split for clarity:

- **Sensors**  
  Day-to-day values (job status, progress, print volume, consumables, HMS sensors)

- **Diagnostics**  
  Firmware, last ping, raw payload, low-level counters

- **Camera** (optional)  
  Print thumbnail proxy (for dashboards)

This keeps dashboards clean while still exposing advanced data when needed.

---

## ✅ Recommended dashboard usage

- Use **Progress**, **Time remaining**, and **Printing** binary sensor for automations.
- Use the **Print thumbnail camera** in a Lovelace picture card for print monitoring.
- Use **Raw payload** when reporting issues — it helps reproduce API differences quickly.

---

## 🧯 Troubleshooting

### Sensors show `Unavailable` or `Unknown`
- Make sure the printer is **online**.
- Restart Home Assistant or reload the integration.
- Check the **Raw payload** diagnostic sensor to confirm what the API returns.

### Thumbnail is sometimes blank
Signed URLs can expire.  
The camera entity keeps the last valid image, but if the printer provides no thumbnail for a job, nothing can be displayed.

---

## 🤝 Contributing

Issues and pull requests are welcome, especially for:
- additional API fields
- better status mappings
- documentation improvements

When opening an issue, please include:
- printer model
- integration version
- relevant **redacted raw payload** section

---

## ⚠️ Disclaimer

This project is **not affiliated with or endorsed by Formlabs**.  
Formlabs® is a registered trademark of Formlabs Inc.
