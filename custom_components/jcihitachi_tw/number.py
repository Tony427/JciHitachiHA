"""JciHitachi integration."""
import datetime
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.util import dt as dt_util

from . import API, COORDINATOR, DOMAIN, JciHitachiEntity

_LOGGER = logging.getLogger(__name__)


async def _async_setup(hass, async_add):
    api = hass.data[DOMAIN][API]
    coordinator = hass.data[DOMAIN][COORDINATOR]

    for thing in api.things.values():
        async_add(
            [JciHitachiMonthlyDataSelectorNumberEntity(thing, coordinator)],
            update_before_add=True
        )

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the number platform."""
    await _async_setup(hass, async_add_entities)

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the number platform from a config entry."""
    await _async_setup(hass, async_add_devices)


class JciHitachiMonthlyDataSelectorNumberEntity(JciHitachiEntity, NumberEntity):
    """Which calendar month the monthly power sensors show: 1-12, the current month by default.

    The number is the month. A month later than the current one means that month of last year,
    because this year's has not happened yet; the month sensor shows the year.

    How the data is read (observed 2026-09-17): `JciHitachiAWSAPI.refresh_monthly_data(n)` asks for
    the last n x 31 days and returns one record per calendar month, oldest first, with
    `Timestamp` at 00:00 UTC on the first day of the month; the monthly sensors show the first
    record. Before this change the number was n itself (1 = current month, 2 = previous one,
    0 = no data), which read like a month number in the UI, and 31-day steps can reach one
    month too far at the start of a month. Now the last 12 months are requested and only the
    record of the chosen month (labelled in UTC, as the cloud aggregates) is kept on the thing,
    so the sensors keep working unchanged.
    """

    _attr_translation_key = "month_selector"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 12
    _attr_native_step = 1

    # 12 x 31 days reaches the same month of last year
    MONTHS_REQUESTED = 12

    def __init__(self, thing, coordinator):
        super().__init__(thing, coordinator)
        self._value = dt_util.now().month

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.hass.async_create_background_task(
            self.hass.async_add_executor_job(self._fetch_month, self._value),
            f"{DOMAIN} monthly data {self._thing.name}",
        )

    @property
    def native_value(self):
        """Return the selected month (1-12)."""
        return self._value

    @property
    def unique_id(self):
        return f"{self._thing.gateway_mac_address}_monthly_data_selector_number"

    @staticmethod
    def target_label(month: int, today: datetime.date) -> str:
        """ "YYYY-MM" of the latest `month` that is not in the future, relative to `today`."""
        year = today.year if month <= today.month else today.year - 1
        return f"{year:04d}-{month:02d}"

    def _fetch_month(self, month) -> bool:
        """Fetch the power data and keep only the chosen month; False when the request failed."""
        api = self.hass.data[DOMAIN][API]
        label = self.target_label(int(month), dt_util.now().date())
        try:
            api.refresh_monthly_data(self.MONTHS_REQUESTED, self._thing.name)
        except Exception as err:  # noqa: BLE001 - the other entities must not be affected
            _LOGGER.warning(f"Could not fetch monthly data for {self._thing.name}: {err}")
            return False
        self._thing.monthly_data = [
            record
            for record in self._thing.monthly_data or []
            if datetime.datetime.fromtimestamp(
                record["Timestamp"] / 1000, tz=datetime.timezone.utc
            ).strftime("%Y-%m")
            == label
        ]
        self.hass.loop.call_soon_threadsafe(self.coordinator.async_update_listeners)
        return True

    def set_native_value(self, value):
        """Set new month."""
        _LOGGER.debug(f"Set {self.name} value to {value}")
        self._value = int(value)
        self._fetch_month(self._value)
        self.schedule_update_ha_state()
