"""JciHitachi integration."""
import logging

from homeassistant.components.binary_sensor import (BinarySensorDeviceClass,
                                                    BinarySensorEntity)
from homeassistant.const import EntityCategory

from . import API, COORDINATOR, DOMAIN, UPDATED_DATA, JciHitachiEntity

_LOGGER = logging.getLogger(__name__)


async def _async_setup(hass, async_add):
    api = hass.data[DOMAIN][API]
    coordinator = hass.data[DOMAIN][COORDINATOR]

    for thing in api.things.values():
        if thing.type == "AC":
            async_add(
                [JciHitachiAttentionBinarySensorEntity(thing, coordinator),
                 JciHitachiFreezeCleanNotificationBinarySensorEntity(thing, coordinator),
                 JciHitachiCleanFilterNotificationBinarySensorEntity(thing, coordinator)],
                update_before_add=True)
        elif thing.type == "DH":
            async_add(
                [JciHitachiErrorBinarySensorEntity(thing, coordinator),
                 JciHitachiWaterFullBinarySensorEntity(thing, coordinator)],
                update_before_add=True)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the binary_sensor platform."""
    await _async_setup(hass, async_add_entities)

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the binary_sensor platform from a config entry."""
    await _async_setup(hass, async_add_devices)


class JciHitachiErrorBinarySensorEntity(JciHitachiEntity, BinarySensorEntity):
    def __init__(self, thing, coordinator):
        super().__init__(thing, coordinator)

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._thing.name} Error"

    @property
    def is_on(self):
        """Indicate whether an error occurred."""
        status = self.hass.data[DOMAIN][UPDATED_DATA].get(self._thing.name, None)
        if status:
            if status.error_code == 0:
                return False
            else:
                return True
        return None

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def unique_id(self):
        return f"{self._thing.gateway_mac_address}_error_binary_sensor"


class JciHitachiWaterFullBinarySensorEntity(JciHitachiEntity, BinarySensorEntity):
    def __init__(self, thing, coordinator):
        super().__init__(thing, coordinator)

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._thing.name} Water Full Warning"

    @property
    def is_on(self):
        """Indicate whether the water tank is full."""
        status = self.hass.data[DOMAIN][UPDATED_DATA].get(self._thing.name, None)
        if status:
            if status.water_full_warning == "off":
                return False
            elif status.water_full_warning == "on":
                return True
        return None

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM
    
    @property
    def unique_id(self):
        return f"{self._thing.gateway_mac_address}_water_full_binary_sensor"


class JciHitachiAttentionBinarySensorEntity(JciHitachiEntity, BinarySensorEntity):
    """On when the backend could not refresh this device (timeout or undecodable answer).

    Stays available while the device itself is unavailable: it is the entity that explains why.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._thing.name} Attention Required"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self):
        return self._thing.attention_reason is not None

    @property
    def extra_state_attributes(self):
        return {"reason": self._thing.attention_reason}

    @property
    def unique_id(self):
        return f"{self._thing.gateway_mac_address}_attention_binary_sensor"


class _JciHitachiShadowNotificationBinarySensorEntity(JciHitachiEntity, BinarySensorEntity):
    """A notification flag from the device's `info` shadow (what the official app shows).

    The shadow is read independently of the status channel, so this works even while the
    status/support requests are failing.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    shadow_key: str = ""
    label: str = ""

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._thing.name} {self.label}"

    @property
    def available(self) -> bool:
        return self.shadow_key in self._thing.notifications

    @property
    def is_on(self):
        return self._thing.notifications.get(self.shadow_key)

    @property
    def unique_id(self):
        return f"{self._thing.gateway_mac_address}_{self.shadow_key.lower()}_binary_sensor"


class JciHitachiFreezeCleanNotificationBinarySensorEntity(_JciHitachiShadowNotificationBinarySensorEntity):
    shadow_key = "CleanNotification"
    label = "Freeze Clean Notification"


class JciHitachiCleanFilterNotificationBinarySensorEntity(_JciHitachiShadowNotificationBinarySensorEntity):
    shadow_key = "CleanFilterNotification"
    label = "Clean Filter Notification"