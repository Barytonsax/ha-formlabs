from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FormlabsApi
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = FormlabsApi(
                session=session,
                client_id=user_input[CONF_CLIENT_ID],
                client_secret=user_input[CONF_CLIENT_SECRET],
            )
            try:
                # validate token + printers list
                await api.async_get_token()
                await api.async_list_printers()
            except Exception:
                errors["base"] = "auth"

            if not errors:
                await self.async_set_unique_id("formlabs")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Formlabs", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
