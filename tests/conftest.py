"""template conftest."""
import pytest
from pytest_homeassistant_custom_component.common import (
    assert_setup_component,
    async_mock_service,
)

from homeassistant.setup import async_setup_component

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Auto enable custom integration."""
    yield


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
async def start_ha(hass, domains, config, caplog):
    """Do setup of integration."""
    for domain, count in domains:
        with assert_setup_component(count, domain):
            assert await async_setup_component(
                hass,
                domain,
                config,
            )
        await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def caplog_setup_text(caplog):
    """Return setup log of integration."""
    yield caplog.text
