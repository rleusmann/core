import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP
)
from homeassistant.components.media_player import MediaPlayerDevice, PLATFORM_SCHEMA
import logging
import serial
import voluptuous as vol

DEFAULT_TIMEOUT = 0.5
DEFAULT_WRITE_TIMEOUT = 0.5
DEFAULT_MIN_VOLUME = -90
DEFAULT_MAX_VOLUME = 10
DEFAULT_NAME = "Cambridge Audio CXR 200"


__version__ = "0.1"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.string,
        vol.Optional(CONF_WRITE_TIMEOUT, default=DEFAULT_WRITE_TIMEOUT): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME),
        vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): cv.string
    }
)

NORMAL_INPUTS_CXR200 = {
    "Source 1": "#3,04,00",
    "Source 2": "#3,04,01",
    "Source 3": "#3,04,02",
    "Source 4": "#3,04,03",
    "Source 5": "#3,04,04",
    "Source 6": "#3,04,05",
    "Source 7": "#3,04,06",
    "Source 8": "#3,04,07",
    "TV ARC": "#3,04,08",
    "Stream Magic": "#3,04,09",
    "MP3": "#3,04,10",
    "FM": "#3,04,11",
    "AM": "#3,04,12",
    "Spotify": "#3,04,13",
    "Bluetooth": "#3,04,14"
}

NORMAL_INPUTS_AMP_REPLY_CXR200 = {
    "#4,01,00": "Source 1",
    "#4,01,01": "Source 2",
    "#4,01,02": "Source 3",
    "#4,01,03": "Source 4",
    "#4,01,04": "Source 5",
    "#4,01,05": "Source 6",
    "#4,01,06": "Source 7",
    "#4,01,07": "Source 8",
    "#4,01,08": "TV ARC",
    "#4,01,09": "Stream Magic",
    "#4,01,10": "MP3",
    "#4,01,11": "FM",
    "#4,01,12": "AM",
    "#4,01,13": "Spotify",
    "#4,01,14": "Bluetooth"
}

# AMP_CMD_SOUND

ERROR_REPLY_GRP_UNKNOWN = '#0,01'
ERROR_REPLY_NR_UNKNOWN = '#0,02'
ERROR_REPLY_DAT_ERR = '#0,03'
ERROR_REPLY_NOT_AVAILABLE = '#0,04'

AMP_CMD_GET_PWSTATE = "#1,01"
AMP_CMD_GET_CURRENT_SOURCE = "#3,01"
AMP_CMD_GET_MUTE_STATE = "#1,03"
AMP_CMD_GET_VOLUME = "#1,05"

AMP_CMD_SET_MUTE_ON = "#1,04,1"
AMP_CMD_SET_MUTE_OFF = "#1,04,0"
AMP_CMD_SET_PWR_ON = "#1,02,1"
AMP_CMD_SET_PWR_OFF = "#1,02,0"
AMP_CMD_SET_VOLUME = "#1,08,"  # join decibel input
AMP_CMD_SET_VOL_STEP_UP = "#1,06"
AMP_CMD_SET_VOL_STEP_DOWN = "#1,07"

AMP_REPLY_PWR_ON = "#2,01,1"
AMP_REPLY_PWR_STANDBY = "#2,01,0"
AMP_REPLY_MUTE_ON = "#2,03,1"
AMP_REPLY_MUTE_OFF = "#2,03,0"


def setup_platform(hass, config, add_devices, discovery_info=None):
    serial_port = config.get(CONF_SERIAL_PORT)
    name = config.get(CONF_NAME)
    timeout = config.get(CONF_TIMEOUT)
    timeout_write = config.get(CONF_WRITE_TIMEOUT)
    min_volume = config.get(CONF_MIN_VOLUME)
    max_volume = config.get(CONF_MAX_VOLUME)

    if serial_port is None:
        _LOGGER.error("No Serial Port found in configuration.yaml")
        return

    add_devices([CambridgeAudioSerial(serial_port, name,
                                      timeout, timeout_write, min_volume, max_volume)])


class CambridgeAudioSerial(MediaPlayerDevice):
    """Cambridge Audio Serial."""

    def __init__(self, serial_port, timeout, write_timeout):
        _LOGGER.info("Create RS232 connection")
        self.ser = serial.Serial(serial_port, baudrate=9600, bytesize=8,
                                 parity='N', stopbits=1, timeout=timeout, write_timeout=write_timeout)
        # self.lock = threading.Lock()

        _LOGGER.info("Setting up Cambridge CXA")
        self._mediasource = ""
        self._speakersactive = ""
        self._muted = AMP_REPLY_MUTE_OFF
        self._name = name
        self._pwstate = ""
        self._source_list = NORMAL_INPUTS_CXR200.copy()
        self._source_reply_list = NORMAL_INPUTS_AMP_REPLY_CXR200.copy()
        self._sound_mode_list = SOUND_MODES.copy()
        self._state = STATE_OFF
        self.update()

    def update(self):
        self._pwstate = self.ser_write(AMP_CMD_GET_PWSTATE)
        _LOGGER.debug("CXA - update called. State is: %s", self._pwstate)
        if AMP_REPLY_PWR_ON in self._pwstate:
            self._mediasource = self.ser_write(AMP_CMD_GET_CURRENT_SOURCE)
            _LOGGER.debug(
                "CXR - get current source called. Source is: %s", self._mediasource)

            self._muted = self.ser_write(AMP_CMD_GET_MUTE_STATE)
            _LOGGER.debug("CXR - current mute state is: %s", self._muted)

    def ser_command(self, command):
        """Write `command` and read answer."""
        _LOGGER.debug("Sending command: %s", command)
        final_command = ''.join([command, '\r']).encode('ascii')
        ser.reset_output_buffer()
        ser.reset_input_buffer()
        self.ser.write(final_command)
        reply = self.ser.read_until(b'\r').decode()
        length = len(reply)
        result = reply[:length - 1]
        _LOGGER.debug("Receiving reply: %s", result)

        if result == ERROR_REPLY_GRP_UNKNOWN:
            _LOGGER.error("The Command Group is invalid")
            return
            elif result == ERROR_REPLY_NR_UNKNOWN:
                _LOGGER.error("The Command Number is invalid for this Group")
                return
            elif result == ERROR_REPLY_DAT_ERR:
                _LOGGER.error("The data is not in the expected range")
                return
            elif result == ERROR_REPLY_NOT_AVAILABLE:
                _LOGGER.error("The command is valid, but can't be actioned")
                return
            return result

    def calc_volume(self, decibel):
        """
        Calculate the volume given the decibel.
        Return the volume (0..1).
        """
        return abs(self._min_volume - decibel) / abs(self._min_volume - self._max_volume)

    def calc_db(self, volume):
        """
        Calculate the decibel given the volume.
        Return the dB.
        """
        return self._min_volume + round(abs(self._min_volume - self._max_volume) * volume)

    @property
    def state(self):
        """State of the player."""
        if AMP_REPLY_PWR_ON in self._pwstate:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def name(self):
        return self._name

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        reply = ser_command(AMP_CMD_GET_VOLUME)
        decibel = int(reply.split(",")[2])
        return calc_volume(decibel)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        if AMP_REPLY_MUTE_ON in self._muted:
            return True
        else:
            return False

    @property
    def source(self):
        """Name of the current input source."""
        return self._source_reply_list[self._mediasource]

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_reply_list[self._mediasource]

    @property
    def sound_mode(self):
        """Name of the current sound mode."""
        return None

    @property
    def sound_mode_list(self):
        """List of available sound modes."""
        return sorted(list(self._sound_mode_list.keys()))

    def turn_on(self):
        """Turn the media player on."""
        ser_command(AMP_CMD_SET_PWR_ON)

    # async def async_turn_on(self):
    #     """Turn the media player on."""
    #     await self.hass.async_add_executor_job(self.turn_on)

    def turn_off(self):
        """Turn the media player off."""
        ser_command(AMP_CMD_SET_PWR_OFF)

    # async def async_turn_off(self):
    #     """Turn the media player off."""
    #     await self.hass.async_add_executor_job(self.turn_off)

    def mute_volume(self, mute):
        """Mute the volume."""
        if mute:
            ser_command(AMP_CMD_SET_MUTE_ON)
        else:
            ser_command(AMP_CMD_SET_MUTE_OFF)

    # async def async_mute_volume(self, mute):
    #     """Mute the volume."""
    #     await self.hass.async_add_executor_job(self.mute_volume, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        ser_command(AMP_CMD_SET_VOLUME + str(calc_db(volume)))

    # async def async_set_volume_level(self, volume):
    #     """Set volume level, range 0..1."""
    #     await self.hass.async_add_executor_job(self.set_volume_level, volume)

    def select_source(self, source):
        """Select input source."""
        ser_command(self._source_list[source])

    # async def async_select_source(self, source):
    #     """Select input source."""
    #     await self.hass.async_add_executor_job(self.select_source, source)

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        raise NotImplementedError()

    # async def async_select_sound_mode(self, sound_mode):
    #     """Select sound mode."""
    #     await self.hass.async_add_executor_job(self.select_sound_mode, sound_mode)
