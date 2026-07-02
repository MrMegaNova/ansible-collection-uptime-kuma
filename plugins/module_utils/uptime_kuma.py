# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json
import time
import traceback
from ansible.module_utils.urls import open_url

SOCKETIO_IMPORT_ERROR = None
try:
    import socketio
except ImportError:
    socketio = None
    SOCKETIO_IMPORT_ERROR = traceback.format_exc()


def connection_argument_spec():
    """Argument spec for the connection options shared by every module.

    Mirrors the C(connection) documentation fragment.
    """
    return dict(
        api_url=dict(type="str", required=True),
        api_username=dict(type="str", required=True),
        api_password=dict(type="str", required=True, no_log=True),
        api_mfa_token=dict(type="str", default="", no_log=True),
        api_timeout=dict(type="int", default=30),
    )


class UptimeKumaError(Exception):
    """Raised on connection, authentication or API call errors."""


class UptimeKumaClient:
    """Minimal Socket.IO client for the Uptime Kuma (>= 2.0) API.

    Only implements what the modules of this collection need.
    """

    def __init__(self, url, timeout=30):
        if socketio is None:
            raise UptimeKumaError(
                "The 'python-socketio' package is required: %s" % SOCKETIO_IMPORT_ERROR
            )
        self.url = url.rstrip("/")
        self.timeout = timeout
        # Lists are pushed by the server (after login or on request),
        # as dicts keyed by id (str).
        self.pushed = {
            "monitorList": None,
            "maintenanceList": None,
            "statusPageList": None,
            "notificationList": None,
        }
        self.sio = socketio.Client(reconnection=False)
        for event in self.pushed:
            self.sio.on(event, self._make_push_handler(event))

    def _make_push_handler(self, event):
        def handler(data):
            self.pushed[event] = data or {}
        return handler

    def connect(self):
        try:
            self.sio.connect(
                self.url, transports=["websocket"], wait_timeout=self.timeout
            )
        except Exception as exc:
            raise UptimeKumaError("Could not connect to %s: %s" % (self.url, exc))

    def disconnect(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass

    def call(self, event, data=None):
        """Call a Socket.IO event and validate the {ok: ...} response."""
        try:
            response = self.sio.call(event, data=data, timeout=self.timeout)
        except socketio.exceptions.TimeoutError:
            raise UptimeKumaError(
                "Call '%s' timed out after %ss" % (event, self.timeout)
            )
        if isinstance(response, dict) and not response.get("ok", True):
            raise UptimeKumaError(
                "Call '%s' failed: %s" % (event, response.get("msg", "unknown error"))
            )
        return response

    def login(self, username, password, mfa_token=""):
        self.call(
            "login",
            {"username": username, "password": password, "token": mfa_token},
        )

    def _fetch_pushed_list(self, call_event, push_event):
        """Request a list; the server acks {ok} and pushes it as an event."""
        self.pushed[push_event] = None
        self.call(call_event)
        deadline = time.monotonic() + self.timeout
        while self.pushed[push_event] is None:
            if time.monotonic() > deadline:
                raise UptimeKumaError(
                    "Timed out waiting for the '%s' push" % push_event
                )
            time.sleep(0.05)
        return self.pushed[push_event]

    def _wait_pushed_list(self, push_event):
        """Wait for a list the server only pushes at login (no request event)."""
        deadline = time.monotonic() + self.timeout
        while self.pushed[push_event] is None:
            if time.monotonic() > deadline:
                raise UptimeKumaError(
                    "Timed out waiting for the '%s' push" % push_event
                )
            time.sleep(0.05)
        return self.pushed[push_event]

    def get_monitors(self):
        return self._fetch_pushed_list("getMonitorList", "monitorList")

    def get_status_pages(self):
        # Pushed once during login; there is no on-demand request event.
        return list(self._wait_pushed_list("statusPageList").values())

    def get_maintenances(self):
        maintenances = self._fetch_pushed_list(
            "getMaintenanceList", "maintenanceList"
        )
        return list(maintenances.values())

    def add_maintenance(self, maintenance):
        return self.call("addMaintenance", maintenance)["maintenanceID"]

    def edit_maintenance(self, maintenance):
        return self.call("editMaintenance", maintenance)["maintenanceID"]

    def get_maintenance_monitors(self, maintenance_id):
        return self.call("getMonitorMaintenance", maintenance_id)["monitors"]

    def set_maintenance_monitors(self, maintenance_id, monitors):
        # Server-side this replaces the whole assignment (delete + insert).
        self.call("addMonitorMaintenance", (maintenance_id, monitors))

    def get_maintenance_status_pages(self, maintenance_id):
        return self.call("getMaintenanceStatusPage", maintenance_id)["statusPages"]

    def set_maintenance_status_pages(self, maintenance_id, status_pages):
        # Server-side this replaces the whole assignment (delete + insert).
        self.call("addMaintenanceStatusPage", (maintenance_id, status_pages))

    def pause_maintenance(self, maintenance_id):
        self.call("pauseMaintenance", maintenance_id)

    def resume_maintenance(self, maintenance_id):
        self.call("resumeMaintenance", maintenance_id)

    def delete_maintenance(self, maintenance_id):
        self.call("deleteMaintenance", maintenance_id)

    # --- Tags -----------------------------------------------------------
    # 'getTags' returns the list directly in its ack (no push).
    def get_tags(self):
        return self.call("getTags")["tags"]

    def add_tag(self, tag):
        return self.call("addTag", tag)["tag"]

    def edit_tag(self, tag):
        return self.call("editTag", tag)["tag"]

    def delete_tag(self, tag_id):
        self.call("deleteTag", tag_id)

    # --- Notifications --------------------------------------------------
    # 'notificationList' is pushed as a list at login only (no request event).
    def get_notifications(self):
        return self._wait_pushed_list("notificationList")

    def add_notification(self, notification, notification_id=None):
        # notification_id=None -> add; otherwise edit that notification.
        return self.call("addNotification", (notification, notification_id))["id"]

    def delete_notification(self, notification_id):
        self.call("deleteNotification", notification_id)

    # --- Monitors -------------------------------------------------------
    def get_monitor(self, monitor_id):
        return self.call("getMonitor", monitor_id)["monitor"]

    def add_monitor(self, monitor):
        return self.call("add", monitor)["monitorID"]

    def edit_monitor(self, monitor):
        return self.call("editMonitor", monitor)["monitorID"]

    def delete_monitor(self, monitor_id, delete_children=False):
        self.call("deleteMonitor", (monitor_id, delete_children))

    def pause_monitor(self, monitor_id):
        self.call("pauseMonitor", monitor_id)

    def resume_monitor(self, monitor_id):
        self.call("resumeMonitor", monitor_id)

    # --- Status pages ---------------------------------------------------
    # Creation is two-step: addStatusPage(title, slug) then saveStatusPage(...).
    def get_status_page(self, slug):
        return self.call("getStatusPage", slug)

    def get_status_page_public(self, slug):
        """Fetch the public JSON of a status page (config + publicGroupList).

        'getStatusPage' does not return the group/monitor layout, so read it
        from the public HTTP endpoint to preserve or diff the monitor groups.
        """
        url = "%s/api/status-page/%s" % (self.url, slug)
        try:
            response = open_url(url, timeout=self.timeout)
            return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise UptimeKumaError(
                "Could not read public status page '%s': %s" % (slug, exc)
            )

    def add_status_page(self, title, slug):
        self.call("addStatusPage", (title, slug))

    def save_status_page(self, slug, config, img_data_url=None, public_group_list=None):
        return self.call(
            "saveStatusPage", (slug, config, img_data_url, public_group_list or [])
        )

    def delete_status_page(self, slug):
        self.call("deleteStatusPage", slug)
