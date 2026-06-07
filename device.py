import logging
from collections.abc import Callable
from datetime import datetime

from redzoo.database.simple import SimpleDB
from abc import ABC, abstractmethod
from threading import Thread
from typing import List, Set, Any
from time import sleep
import enocean.utils
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.constants import PACKET, RORG
import queue



class Device(ABC):

    def __init__(self, name: str):
        self.name = name
        self.listeners: Set[Callable[['Device'], None]] = set()

    def register_listener(self, listener: Callable[['Device'], None]):
        self.listeners.add(listener)

    def _notify_listeners(self):
        for listener in self.listeners:
            listener(self)

    @abstractmethod
    def handle_packet(self, packet) -> bool:
        pass



class WindowHandle(Device):

    @staticmethod
    def supports(eep_id: str) -> bool:
        return eep_id.upper() == 'F6:10:00'

    def __init__(self, name: str, directory: str, eep_id: str, enocean_id: str):
        self.db = SimpleDB(f"processing_state_{eep_id}_{enocean_id}", directory=directory)
        self.sender = enocean_id.upper()
        self.sender_hex_string: List[int] = enocean.utils.from_hex_string(self.sender)
        self.eep_id = eep_id.upper()
        self.eep_id_hex_string: List[int] = enocean.utils.from_hex_string(self.eep_id)
        self.last_state_update = datetime.now()
        logging.info(f"window handle (eep_id: {eep_id}, enocean_id: {enocean_id})")
        super().__init__(name)

    @property
    def closed(self) -> bool:
        return self.state_text == "CLOSED"

    @property
    def state_text(self) -> str:
        if self.state == 1:
            return "TILTED"
        elif self.state == 2:
            return "OPEN"
        else:
            return "CLOSED"

    @property
    def state(self) -> int:
        return self.db.get("state", 3)

    def __set_state(self, state: int):
        previous_state = self.db.get("state", -1)
        if previous_state != state:
            self.db.put("state", state)
            logging.info(f"{self.name} state updated {self.state} ({self.state_text})")
            self.last_state_update = datetime.now()
            self._notify_listeners()

    def handle_packet(self, packet: Any) -> bool:
        try:
            if self.eep_id_hex_string[0] == 0xf6 and packet.packet_type == PACKET.RADIO_ERP1 and packet.rorg == RORG.RPS:
                packet.parse_eep(self.eep_id_hex_string[1], self.eep_id_hex_string[2])
                state = packet.parsed['WIN']['raw_value']  #  WIN: {'description': 'Window handle', 'unit': '', 'value': 'Moved from vertical to down', 'raw_value': 3}
                if self.sender == packet.sender_hex:
                    self.__set_state(state)
                    return True
        except Exception:
            logging.exception("error occurred by handling packet")
        return False


class Enocean:

    def __init__(self, port: str, devices: List[Device]):
        self.running = True
        self.devices = devices
        self.communicator = SerialCommunicator(port=port)

    def stop(self):
        self.running= False

    def receive(self, background: bool = False):
        if background:
            Thread(target=self.__receive, daemon=True).start()
        else:
            self.__receive()

    def __receive(self):
        try:
            self.communicator.start()
            if self.communicator.base_id is None:
                logging.warning('init failed')
            else:
                logging.info(f"The Base ID of your module is {enocean.utils.to_hex_string(self.communicator.base_id)}")

            # endless loop receiving radio packets
            while self.communicator.is_alive() and self.running:
                try:
                    # Loop to empty the queue...
                    packet = self.communicator.receive.get(block=True, timeout=1)
                    for device in self.devices:
                        is_handled = device.handle_packet(packet)
                        if is_handled:
                            break
                except queue.Empty:
                    sleep(0.5)
                    continue
                except KeyboardInterrupt:
                    break
                except Exception:
                    logging.exception("error occurred by processing packet")
                    sleep(2)
        finally:
            self.communicator.stop()
