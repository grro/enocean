import logging
import argparse
from time import sleep
from typing import List, Optional
from webthing import (MultipleThings, WebThingServer)

from device import WindowHandle, Enocean, Device
from enocean_mcp import EnoceanMCPServer
from enocean_webthing import WindowHandleWebThing


def run_server(
    description: str,
    directory: str,
    port: int,
    path: str,
    addresses: List[str],
    mcp_enabled: bool = True,
    mcp_port: Optional[int] = None,
    mcp_host: str = "0.0.0.0",
    mcp_name: str = "WindowHandles",
):
    devices: List[Device] = []
    for address in sorted(addresses):
        name, eep_id, enocean_id = address.split("/")
        if WindowHandle.supports(eep_id):
            devices.append( WindowHandle(name, directory, eep_id, enocean_id))
        else:
            logging.warning("unsupported device (eep_id: " + eep_id + ", enocean_id: " + enocean_id +"). Ignoring it")
    enocean = Enocean(path, devices)

    server = WebThingServer(
        MultipleThings([WindowHandleWebThing(description, device) for device in devices], 'devices'),
        port=port,
        disable_host_validation=True,
    )

    resolved_mcp_port = mcp_port if mcp_port is not None else port + 2
    mcp_server = EnoceanMCPServer(mcp_name, resolved_mcp_port, devices, host=mcp_host) if mcp_enabled else None

    try:
        logging.info('starting the server (port: ' + str(port) + ')')
        if mcp_server is not None:
            logging.info('starting MCP server (name: %s, host: %s, port: %s)', mcp_name, mcp_host, resolved_mcp_port)
        enocean.receive(background=True)
        if mcp_server is not None:
            mcp_server.start()
        server.start()
    except KeyboardInterrupt:
        logging.info('stopping the server')
        if mcp_server is not None:
            mcp_server.stop()
        server.stop()
        enocean.stop()
        logging.info('done')
        return
    except Exception as e:
        logging.error(e)
        if mcp_server is not None:
            mcp_server.stop()
        enocean.stop()
        sleep(3)




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EnOcean WebThing + optional MCP server")
    parser.add_argument("directory", help="Directory used for persistent processing state")
    parser.add_argument("port", type=int, help="WebThing HTTP port")
    parser.add_argument("path", help="Serial device path (e.g. /dev/ttyUSB0)")
    parser.add_argument("devices", help="Comma-separated devices in format name/eep_id/enocean_id")

    parser.add_argument("--description", default="description", help="WebThing description")
    parser.add_argument("--mcp-enabled", dest="mcp_enabled", action="store_true", default=True, help="Enable MCP server")
    parser.add_argument("--mcp-disabled", dest="mcp_enabled", action="store_false", help="Disable MCP server")
    parser.add_argument("--mcp-port", type=int, default=None, help="MCP server port (default: webthing port + 2)")
    parser.add_argument("--mcp-host", default="0.0.0.0", help="MCP bind host")
    parser.add_argument("--mcp-name", default="WindowHandles", help="MCP service name")
    return parser.parse_args()


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(name)-20s: %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger('tornado.access').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    args = parse_args()
    run_server(
        args.description,
        args.directory,
        args.port,
        args.path,
        [addr.strip() for addr in args.devices.split(",") if addr.strip()],
        mcp_enabled=args.mcp_enabled,
        mcp_port=args.mcp_port,
        mcp_host=args.mcp_host,
        mcp_name=args.mcp_name,
    )



