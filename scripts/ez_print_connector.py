#!/usr/bin/env python3
"""EZ Print Connector for local LAN/USB ESC/POS receipt printers.

Run on a computer / mini-PC inside the merchant's network.
No inbound ports or public IP required. The server never connects to LAN devices.

Example LAN:
  EZ_PRINT_TOKEN=... python scripts/ez_print_connector.py \
    --server https://ez-thing-staging.onrender.com --device-id UUID \
    --mode lan --host 192.168.1.200 --port 9100

Example USB (optional dependency: pip install pyusb):
  EZ_PRINT_TOKEN=... python scripts/ez_print_connector.py \
    --server https://... --device-id UUID --mode usb \
    --usb-vendor 0x04b8 --usb-product 0x0202

USB VID/PID above are illustrative; verify with your actual printer before use.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import json
from pathlib import Path


def escpos_bytes(text: str) -> bytes:
    # Portable fallback for generic ESC/POS hardware/codepages. Future
    # model-specific drivers may render Vietnamese as bitmaps when supported.
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFKD", text)
    ascii_text = text.encode("ascii", errors="replace")
    return b"\x1b@" + ascii_text + b"\n\n\x1dV\x00"


def send_lan(raw: bytes, host: str, port: int, timeout: float = 12):
    # Only this local agent can access its configured printer IP.
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(raw)


def send_usb(raw: bytes, vendor_id: int, product_id: int):
    try:
        import usb.core
        import usb.util
    except ImportError as exc:
        raise RuntimeError("USB mode requires: pip install pyusb") from exc
    dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
    if dev is None:
        raise RuntimeError("USB printer not found. Verify VID/PID and USB permissions.")
    dev.set_configuration()
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    endpoint = usb.util.find_descriptor(
        intf, custom_match=lambda x:
        usb.util.endpoint_direction(x.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    if endpoint is None:
        raise RuntimeError("No USB bulk OUT endpoint detected")
    endpoint.write(raw, timeout=12000)
    usb.util.dispose_resources(dev)


def request_json(base: str, token: str, path: str, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method="POST" if body is not None else "GET",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def run(args):
    base = args.server.rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" and not (
            os.getenv("EZ_PRINT_ALLOW_HTTP_DEV") == "1"
            and parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        raise ValueError("HTTPS is required for print device credentials")
    if args.mode == "lan" and (not args.host or not 1 <= args.port <= 65535):
        raise ValueError("LAN mode requires --host and valid --port")
    if args.mode == "usb" and (args.usb_vendor is None or args.usb_product is None):
        raise ValueError("USB mode requires --usb-vendor and --usb-product")
    token = os.getenv("EZ_PRINT_TOKEN", "")
    if len(token) < 32:
        raise ValueError("Set EZ_PRINT_TOKEN with the one-time secret from EZ Thing")
    path = "/api/print/connector/" + urllib.parse.quote(args.device_id, safe="")
    print("EZ Print Connector ready. Device:", args.device_id, "Mode:", args.mode)
    while True:
        try:
            response = request_json(base, token, path + "/next")
            job = response.get("job")
            if not job:
                time.sleep(max(2, min(30, response.get("poll_after_seconds", 3))))
                continue
            result = {"job_id": job["id"], "success": False, "error": ""}
            try:
                raw = escpos_bytes(job["content"])
                if args.mode == "lan":
                    send_lan(raw, args.host, args.port)
                else:
                    send_usb(raw, args.usb_vendor, args.usb_product)
                result["success"] = True
            except Exception as exc:
                result["error"] = str(exc)[:200]
                print("Print failure:", result["error"], file=sys.stderr)
            # If ACK is lost, queue is held for manager review to avoid
            # possible duplicate paper tickets. No automatic retry here.
            request_json(base, token, path + "/ack", result)
            print("Acknowledged job:", job["id"], "transport_ok=", result["success"])
        except KeyboardInterrupt:
            print("\nConnector stopped")
            break
        except urllib.error.HTTPError as exc:
            print("Cloud API HTTP error:", exc.code, file=sys.stderr)
            if exc.code in (401, 403, 404):
                break
            time.sleep(10)
        except Exception as exc:
            print("Connector error:", str(exc)[:240], file=sys.stderr)
            time.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EZ Thing LAN/USB print connector")
    parser.add_argument("--server", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--mode", choices=["lan", "usb"], required=True)
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--usb-vendor", type=lambda x: int(x, 0))
    parser.add_argument("--usb-product", type=lambda x: int(x, 0))
    try:
        run(parser.parse_args())
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
