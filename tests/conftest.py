"""template conftest."""
import json
import time

import pytest

from homeassistant import loader
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import assert_setup_component, async_mock_service

pytest_plugins = "pytest_homeassistant_custom_component"

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def start_ha(hass, domains, caplog):
    """Do setup of integration."""
    for domain, value in domains.items():
        with assert_setup_component(value['count'], domain):
            assert await async_setup_component(
                hass,
                domain,
                value['config'],
            )
            await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

@pytest.fixture
async def caplog_setup_text(caplog):
    """Return setup log of integration."""
    yield caplog.text
