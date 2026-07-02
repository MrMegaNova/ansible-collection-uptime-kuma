#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Initialise a throwaway Uptime Kuma instance for integration tests.

Waits for the HTTP endpoint, provisions the SQLite database, waits for the
internal restart, then creates the admin account over the Socket.IO API.
Configuration comes from the environment: KUMA_URL, KUMA_USER, KUMA_PASS.
"""
from __future__ import absolute_import, division, print_function

import json
import os
import sys
import time

from urllib.request import Request, urlopen

import socketio

URL = os.environ.get("KUMA_URL", "http://127.0.0.1:3001")
USER = os.environ.get("KUMA_USER", "admin")
PASS = os.environ.get("KUMA_PASS", "Adm1n-Str0ng-Pass!7")


def http_up():
    try:
        urlopen(URL, timeout=5)
        return True
    except Exception:
        return False


def wait_http(timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if http_up():
            return
        time.sleep(2)
    raise SystemExit("Uptime Kuma HTTP endpoint never came up")


def setup_database():
    req = Request(
        URL + "/setup-database",
        data=json.dumps({"dbConfig": {"type": "sqlite"}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    urlopen(req, timeout=30).read()


def create_admin(timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sio = socketio.Client(reconnection=False)
        try:
            sio.connect(URL, transports=["websocket"], wait_timeout=10)
            resp = sio.call("setup", data=(USER, PASS), timeout=20)
            if isinstance(resp, dict) and (
                resp.get("ok") or "initialized" in (resp.get("msg") or "")
            ):
                return
        except Exception:
            pass
        finally:
            try:
                sio.disconnect()
            except Exception:
                pass
        time.sleep(3)
    raise SystemExit("Could not create the admin account")


def main():
    wait_http()
    setup_database()
    time.sleep(20)  # internal restart after DB provisioning
    wait_http()
    create_admin()
    sys.stdout.write("Uptime Kuma ready\n")


if __name__ == "__main__":
    main()
