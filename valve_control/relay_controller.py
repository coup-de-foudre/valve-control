# This file is part of the CdF Valve Control software.
#
# Copyright (C) 2019, Michael McCoy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import logging
from contextlib import contextmanager
from enum import Enum
import subprocess
from typing import List


_GPIO_PATH = "/sys/class/gpio/gpio{channel}"
_EXPORT_PATH = "/sys/class/gpio/export"
_UNEXPORT_PATH = "/sys/class/gpio/unexport"

RELAY_1_GPIO_PIN = 26
RELAY_2_GPIO_PIN = 20
RELAY_3_GPIO_PIN = 21


def _logger():
    return logging.getLogger(__name__)


class Value(Enum):
    ON = 0
    OFF = 1


class Relay:

    DIRECTION = b"out"
    _ON_VALUE = b"0"
    _OFF_VALUE = b"1"

    def __init__(self, channel):
        # type: (int) -> None
        self._channel = channel
        self._channel_bytes = "{channel}".format(channel=self._channel).encode()

        self._path = _GPIO_PATH.format(channel=self._channel)
        self._value_path = os.path.join(self._path, "value")
        self._export_path = _EXPORT_PATH
        self._unexport_path = _UNEXPORT_PATH
        self._direction_path = os.path.join(self._path, "direction")

        self._set_up()

    def __del__(self):
        self._shut_down()

    def _set_up(self):
        # type: () -> None
        _logger().debug("Setting up channel %s", self._channel)
        try:
            _logger().debug("Turning on export")
            with open(self._export_path, "wb") as fp:
                fp.write(self._channel_bytes)
        except Exception as e:
            _logger().debug(
                "Unable to turn on export for channel %s: may be enabled already: %s",
                self.channel, e)
        with open(self._direction_path, "rb") as fp:
            self._original_direction = fp.read()
        with open(self._direction_path, "wb") as fp:
            fp.write(self.DIRECTION)
        self.value = Value.OFF

    def _shut_down(self):
        _logger().debug("Shutting down channel %s", self._channel)
        self.value = Value.OFF
        try:
            _logger().debug("Turning off export")
            with open(self._unexport_path, "wb") as fp:
                fp.write(self._channel_bytes)
        except Exception as e:
            _logger().warning(
                "Unable to turn off export for channel %s: %s",
                self.channel, e)

    @property
    def channel(self):
        # type: () -> int
        return self._channel

    @property
    def value(self):
        # type: () -> Value
        logging.debug("Getting value for channel %s", self.channel)
        with open(self._value_path, "rb") as fp:
            return self._raw_value_to_value(fp.read())

    @value.setter
    def value(self, value):
        # type: (Value) -> None
        logging.debug("Setting channel %s to value %s", self.channel, value)
        self._set_raw_value(self._value_to_raw_value(value))

    def toggle(self):
        # type: () -> Value
        """Toggle value; returns new value."""
        _logger().debug("Toggling channel %s", self.channel)
        if self.value is Value.ON:
            self.value = Value.OFF
        else:
            self.value = Value.ON
        return self.value

    def _raw_value_to_value(self, raw_value):
        # type: (bytes) -> Value
        if raw_value.rstrip() == self._ON_VALUE:
            return Value.ON
        elif raw_value.rstrip() == self._OFF_VALUE:
            return Value.OFF
        raise ValueError("Unknown raw_value {}".format(raw_value))

    def _value_to_raw_value(self, value):
        # type: (Value) -> bytes
        if value is Value.ON:
            return self._ON_VALUE
        elif value is Value.OFF:
            return self._OFF_VALUE
        raise ValueError("Unknown value {}".format(value))

    def _set_raw_value(self, value):
        # type:  (bytes) -> bytes
        with open(self._value_path, "rb") as fp:
            previous_value = fp.read()
        with open(self._value_path, "wb") as fp:
            fp.write(value)
        return previous_value


class RelayController:

    def __init__(self):
        self.relays = [
            Relay(channel=RELAY_1_GPIO_PIN),
            Relay(channel=RELAY_2_GPIO_PIN),
            Relay(channel=RELAY_3_GPIO_PIN),
        ]


def _get_midi_port() -> str:
    """Return a MIDI port for the device, if one is availble"""
    _logger().debug("Getting MIDI device")
    popen = subprocess.Popen(
        args=["amidi", "-l"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1,  # line buffered
    )
    try:
        stdout_data, stderr_data = popen.communicate(timeout=5)
    except subprocess.TimeoutExpired as e:
        popen.kill()
        raise e

    _logger().debug("amidi output: %s", stdout_data)
    if stderr_data:
        _logger().warning("amidi  errors: %s", stderr_data)

    return stdout_data.split('\n', 2)[1].split()[1]


@contextmanager
def amidi_process(midi_port: str) -> subprocess.Popen:
    with subprocess.Popen(
            args=["amidi", "-p", midi_port, "-d"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,  # it's gonna be bytes
            bufsize=0,  # unbuffered
            ) as process:
        try:
            _logger().debug("Process started, pid = %s", process.pid)
            yield process
        finally:
            _logger().debug("Killing process, pid = %s", process.pid)
            process.kill()


class MIDIRelayController(RelayController):

    CONTROL_MASK = 0xF0
    CONTROL_NOTE_OFF = 0x80
    CONTROL_NOTE_ON = 0x90

    CHANNEL_MASK = 0x0F

    NOTE_TO_VALUE = {
        60: 1,  # C3
        61: 2,  # Db3
        62: 3,  # D3
        63: 4,  # Eb3
        64: 5,  # E3
        65: 6,  # F3
        66: 7,  # Gb3
    }

    def __init__(self, port: str = None, base_value: int = 0, channel: int = 4):
        super().__init__()
        if port is None:
            port = _get_midi_port()
        self.port = port
        _logger().debug("MIDI port is %s", self.port)
        self.base_value = base_value
        self.channel = channel

    def run_forever(self):
        self.set_value(self.base_value)

        buffer = []
        with amidi_process(self.port) as process:
            process.stdout.readline()
            while True:
                next_byte = process.stdout.read(1)
                if next_byte == b"\n":
                    buffer = []
                    continue
                elif next_byte == b"" and process.poll() is not None:
                    # EOF
                    break
                elif next_byte:
                    _logger().debug("Got byte %s", next_byte)
                    buffer.append(next_byte)
                    self._callback(buffer)
                else:
                    _logger().warning("Next byte: %s, process.poll(): %s",
                                      next_byte, process.poll())
            _logger().warning("Process returned code %s", process.poll())

    def _callback(self, byte_buffer: List[bytes]):
        if not byte_buffer:
            return

        byte_array = b"".join(byte_buffer).split()
        _logger().debug("Received data %s", byte_array)
        try:
            midi_hex = [int(b"0x" + data, base=16) for data in byte_array]
        except ValueError as e:
            _logger().warning("Unable to decode buffer to hex: %s", e)
            return

        try:
            control, *values = midi_hex
        except ValueError:
            # No values, nothing to do
            return

        if control & self.CONTROL_MASK == self.CONTROL_NOTE_OFF:
            # self.set_value(self.base_value)
            _logger.debug("Note off signal ignored ... ")
            return
        elif control & self.CONTROL_MASK == self.CONTROL_NOTE_ON:
            channel = (control & self.CHANNEL_MASK) + 1  # Human channels 1-indexed
            self._set_note_on(channel, *values)
            return
        else:
            _logger().debug("Unknown control signal value %02x", control)
            return

    def _set_note_on(self, channel: int, *values: int):
        _logger().debug("Setting note on: channel %d, values %s", channel, values)
        if channel != self.channel:
            _logger().debug(
                "Not our channel: expecting %d, got %d", self.channel, channel)
            return
        if not values:
            _logger().debug("No values: channel %d, values %s", channel, values)
            return
        self.set_value(self.NOTE_TO_VALUE.get(values[0], self.base_value))

    def set_value(self, value: int):
        if value < 0 or value > 7:
            raise ValueError("Value must be between zero and seven, got %d", value)

        if value & 0x01:
            self.relays[0].value = Value.ON
        else:
            self.relays[0].value = Value.OFF

        if value & 0x02:
            self.relays[1].value = Value.ON
        else:
            self.relays[1].value = Value.OFF

        if value & 0x04:
            self.relays[2].value = Value.ON
        else:
            self.relays[2].value = Value.OFF


def get_char():
    # for POSIX-based systems (with termios & tty support)
    import tty, sys, termios  # raises ImportError if unsupported

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        answer = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return answer


def main():
    logging.basicConfig(level=logging.DEBUG)

    relay_controller = MIDIRelayController()
    relay_controller.run_forever()

    instructions = "Enter 1, 2, or 3 to toggle channel, q to quit"
    print(instructions)
    while True:
        x = input()
        if x == "q":
            break
        elif x in {"1", "2", "3"}:
            relay_controller.relays[int(x) - 1].toggle()
        else:
            print("Invalid choice {}".format(x))
            print(instructions)


if __name__ == "__main__":
    main()
