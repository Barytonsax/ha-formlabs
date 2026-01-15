from __future__ import annotations

DOMAIN = "formlabs"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

DATA_API = "api"
DATA_COORDINATOR = "coordinator"

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

BASE_URL = "https://api.formlabs.com"
# ✅ IMPORTANT: endpoint "developer"
TOKEN_URL = f"{BASE_URL}/developer/v1/o/token/"
API_BASE = f"{BASE_URL}/developer/v1"
