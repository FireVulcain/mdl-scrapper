"""A CONNECT-only proxy that lets the scraper leave through a home connection.

Cloudflare in front of MDL refuses datacenter addresses (Hetzner, Vercel) and
lets residential ones through. This runs on an always-on home machine, listens
on its Tailscale address only, and tunnels the scraper's HTTPS to MDL. The TLS
session is end to end, so primp's browser handshake reaches MDL untouched.

It only opens tunnels to MDL hosts on port 443; anything else is refused, so a
tailnet peer cannot use it as a general-purpose proxy.

    python tools/home_proxy.py 100.x.y.z 8888

The scraper then runs with MDL_PROXY=http://100.x.y.z:8888.
"""

import asyncio
import sys

ALLOWED_HOSTS = ("mydramalist.com", ".mydramalist.com")
ALLOWED_PORT = 443


def allowed(host: str, port: int) -> bool:
    host = host.lower()
    return port == ALLOWED_PORT and (host == ALLOWED_HOSTS[0] or host.endswith(ALLOWED_HOSTS[1]))


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        head = await asyncio.wait_for(client_reader.readuntil(b"\r\n\r\n"), timeout=10)
        method, target, _ = head.split(b"\r\n", 1)[0].decode("latin-1").split(" ", 2)
        host, _, port_text = target.rpartition(":")
        port = int(port_text) if port_text.isdigit() else 0
        if method != "CONNECT" or not allowed(host, port):
            client_writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            await client_writer.drain()
            client_writer.close()
            return

        upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=15)
        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()
        await asyncio.gather(pipe(client_reader, upstream_writer), pipe(upstream_reader, client_writer))
    except Exception:
        client_writer.close()


async def main(bind: str, port: int) -> None:
    server = await asyncio.start_server(handle, bind, port)
    print(f"proxy on {bind}:{port}, tunnelling to {ALLOWED_HOSTS[0]}:{ALLOWED_PORT} only", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: home_proxy.py <tailscale-ip> <port>")
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
