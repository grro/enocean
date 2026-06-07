import sys
import logging
from time import sleep
from typing import Dict, List
from webthing import (MultipleThings, WebThingServer)

from device import WindowHandle, Enocean, Device
from enocean_mcp import EnoceanMCPServer
from enocean_webthing import WindowHandleWebThing


def run_server(description: str, directory: str, port: int, path: str, addresses: List[str]):
    devices: List[Device] = []
    for address in sorted(addresses):
        name, eep_id, enocean_id = address.split("/")
        if WindowHandle.supports(eep_id):
            devices.append( WindowHandle(name, directory, eep_id, enocean_id))
        else:
            logging.warning("unsupported device (eep_id: " + eep_id + ", enocean_id: " + enocean_id +"). Ignoring it")
    enocean = Enocean(path, devices)

    server = WebThingServer(MultipleThings([WindowHandleWebThing(description, device) for device in devices], 'devices'), port=port, disable_host_validation=True)
    mcp_server = EnoceanMCPServer("WindowHandles", port+2, devices)
    try:
        logging.info('starting the server (port: ' + str(port) + ')')
        enocean.receive(background=True)
        mcp_server.start()
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        mcp_server.stop()
        server.stop()
        enocean.stop()
        logging.info('done')
        return
    except Exception as e:
        logging.error(e)
        sleep(3)




if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(name)-20s: %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger('tornado.access').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)
    run_server("description", sys.argv[1], int(sys.argv[2]), sys.argv[3], [addr.strip() for addr in sys.argv[4].split(",")])



