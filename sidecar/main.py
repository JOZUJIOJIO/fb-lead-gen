"""LeadFlow sidecar entry point — JSON-RPC 2.0 server over stdin/stdout."""

import asyncio
import logging
import sys

from jsonrpc import JsonRpcServer

# Configure logging to stderr so stdout stays clean for JSON-RPC traffic
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("leadflow.sidecar")

server = JsonRpcServer()


@server.method("ping")
async def ping() -> str:
    logger.debug("ping received")
    return "pong"


@server.method("get_status")
async def get_status() -> dict:
    logger.debug("get_status received")
    return {
        "version": "0.1.0",
        "db": "not_connected",
    }


if __name__ == "__main__":
    logger.info("LeadFlow sidecar starting")
    asyncio.run(server.run())
    logger.info("LeadFlow sidecar stopped")
