#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: maintenance
short_description: Manage a self-expiring Uptime Kuma maintenance window
description:
  - Create or refresh a time-boxed Uptime Kuma maintenance window (C(single)
    strategy) covering a set of monitors, over the Socket.IO API.
  - The window starts immediately and lasts I(duration_minutes), then expires
    on its own - no teardown call is needed. Uptime Kuma persists the window
    across its own restart, so it keeps covering the monitors while the host
    (which may itself host Uptime Kuma) reboots and its services recover.
  - Targets Uptime Kuma 2.x.
  - The maintenance window is identified by its exact I(title).
author:
  - MrMegaNova (@MrMegaNova)
extends_documentation_fragment:
  - mrmeganova.uptime_kuma.connection
options:
  title:
    description: Exact title of the maintenance window.
    type: str
    required: true
  description:
    description: Description of the maintenance window (set at creation only).
    type: str
    default: ""
  monitors:
    description:
      - Monitor names (exact match) covered by the maintenance window.
      - When omitted, the current assignment is left untouched.
    type: list
    elements: str
  status_pages:
    description:
      - Status pages (by title or slug) the maintenance is shown on.
      - Ignored when I(all_status_pages=true).
      - When both are omitted, the current assignment is left untouched.
    type: list
    elements: str
  all_status_pages:
    description: Show the maintenance on every status page.
    type: bool
    default: false
  duration_minutes:
    description:
      - Length of the maintenance window, starting now.
      - Make it comfortably longer than the update plus reboot and service
        recovery time.
    type: int
    default: 60
  state:
    description:
      - V(present) creates the window if missing, or refreshes it (new time
        window) if it exists and is no longer active.
      - V(paused) ensures the window exists but is paused; it keeps the scope in
        sync without resetting the time window.
      - V(absent) deletes the window.
    type: str
    choices: [present, paused, absent]
    default: present
"""

EXAMPLES = r"""
- name: Open a maintenance window before updating a host
  mrmeganova.uptime_kuma.maintenance:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    title: ansible-update srv-01
    monitors:
      - srv-01 http
      - srv-01 ping
    duration_minutes: 45
  delegate_to: localhost

- name: Remove the maintenance window
  mrmeganova.uptime_kuma.maintenance:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    title: ansible-update srv-01
    state: absent
  delegate_to: localhost
"""

RETURN = r"""
maintenance_id:
  description: Id of the maintenance window, if it exists.
  type: int
  returned: success
  sample: 3
actions:
  description: Actions performed (or that would be performed in check mode).
  type: list
  elements: str
  returned: success
  sample: [created]
"""

from datetime import datetime, timedelta, timezone

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.mrmeganova.uptime_kuma.plugins.module_utils.uptime_kuma import (
    SOCKETIO_IMPORT_ERROR,
    UptimeKumaClient,
    UptimeKumaError,
    connection_argument_spec,
    socketio,
)


def build_maintenance_payload(params):
    """Payload for a single-strategy window running from now (UTC).

    Dates are expressed in UTC so the result does not depend on the
    controller or server timezone.
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(minutes=params["duration_minutes"])
    return {
        "title": params["title"],
        "description": params["description"],
        "strategy": "single",
        "active": True,
        "dateRange": [
            now.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
        ],
        "timeRange": [
            {"hours": 0, "minutes": 0},
            {"hours": 0, "minutes": 0},
        ],
        "intervalDay": 1,
        "weekdays": [],
        "daysOfMonth": [],
        "cron": "",
        "durationMinutes": 0,
        "timezoneOption": "UTC",
    }


def resolve_monitors(client, names):
    """Map monitor names to [{id, name}] payloads.

    Fails on unknown names and on names shared by several monitors.
    """
    by_name = {}
    for monitor in client.get_monitors().values():
        by_name.setdefault(monitor.get("name"), []).append(monitor)
    missing = [n for n in names if n not in by_name]
    if missing:
        raise UptimeKumaError(
            "Unknown monitor(s): %s. Available: %s"
            % (", ".join(missing), ", ".join(sorted(by_name)))
        )
    ambiguous = [n for n in names if len(by_name[n]) > 1]
    if ambiguous:
        raise UptimeKumaError(
            "Monitor name(s) matching several monitors: %s" % ", ".join(ambiguous)
        )
    return [{"id": by_name[n][0]["id"], "name": n} for n in names]


def resolve_status_pages(client, params):
    """Return the desired status page assignment as [{id}], or None to skip.

    Honours I(all_status_pages) first, then an explicit I(status_pages) list
    matched by title or slug.
    """
    pages = client.get_status_pages()
    if params["all_status_pages"]:
        return [{"id": p["id"]} for p in pages]
    names = params["status_pages"]
    if not names:
        return None
    by_key = {}
    for page in pages:
        by_key.setdefault(page.get("title"), page)
        by_key.setdefault(page.get("slug"), page)
    missing = [n for n in names if n not in by_key]
    if missing:
        raise UptimeKumaError(
            "Unknown status page(s): %s. Available: %s"
            % (
                ", ".join(missing),
                ", ".join(sorted(p.get("title") for p in pages)),
            )
        )
    return [{"id": by_key[n]["id"]} for n in names]


def run(module, client):
    params = module.params
    result = {"changed": False, "actions": [], "maintenance_id": None}

    client.login(
        params["api_username"], params["api_password"], params["api_mfa_token"]
    )

    existing = None
    for maintenance in client.get_maintenances():
        if maintenance.get("title") == params["title"]:
            existing = maintenance
            result["maintenance_id"] = maintenance["id"]
            break

    if params["state"] == "absent":
        if existing:
            result["changed"] = True
            result["actions"].append("deleted")
            if not module.check_mode:
                client.delete_maintenance(existing["id"])
        return result

    desired_monitors = None
    if params["monitors"]:
        desired_monitors = resolve_monitors(client, params["monitors"])
    desired_status_pages = resolve_status_pages(client, params)

    if not existing:
        result["changed"] = True
        result["actions"].append("created")
        if not module.check_mode:
            maintenance_id = client.add_maintenance(
                build_maintenance_payload(params)
            )
            result["maintenance_id"] = maintenance_id
            if desired_monitors:
                client.set_maintenance_monitors(maintenance_id, desired_monitors)
            if desired_status_pages is not None:
                client.set_maintenance_status_pages(
                    maintenance_id, desired_status_pages
                )
            if params["state"] == "paused":
                client.pause_maintenance(maintenance_id)
        if params["state"] == "paused":
            result["actions"].append("paused")
        return result

    maintenance_id = existing["id"]

    monitors_match = True
    if desired_monitors is not None:
        current = sorted(
            m.get("id") for m in client.get_maintenance_monitors(maintenance_id)
        )
        monitors_match = current == sorted(m["id"] for m in desired_monitors)

    status_pages_match = True
    if desired_status_pages is not None:
        current = sorted(
            p.get("id")
            for p in client.get_maintenance_status_pages(maintenance_id)
        )
        status_pages_match = current == sorted(
            p["id"] for p in desired_status_pages
        )

    scope_changed = (desired_monitors is not None and not monitors_match) or (
        desired_status_pages is not None and not status_pages_match
    )

    def apply_scope():
        if desired_monitors is not None and not monitors_match:
            client.set_maintenance_monitors(maintenance_id, desired_monitors)
        if desired_status_pages is not None and not status_pages_match:
            client.set_maintenance_status_pages(maintenance_id, desired_status_pages)

    if params["state"] == "paused":
        is_active = bool(existing.get("active"))
        # Already paused and correctly scoped: nothing to do.
        if not is_active and not scope_changed:
            return result
        result["changed"] = True
        if not module.check_mode:
            apply_scope()
            if is_active:
                client.pause_maintenance(maintenance_id)
        if scope_changed:
            result["actions"].append("rescoped")
        if is_active:
            result["actions"].append("paused")
        return result

    # state == present: already covering and correctly scoped -> nothing to do.
    if (
        existing.get("status") == "under-maintenance"
        and monitors_match
        and status_pages_match
    ):
        return result

    # Otherwise refresh the window (expired/ended/paused) and re-scope it.
    result["changed"] = True
    result["actions"].append("refreshed")
    if not module.check_mode:
        payload = build_maintenance_payload(params)
        payload["id"] = maintenance_id
        client.edit_maintenance(payload)
        apply_scope()

    return result


def main():
    argument_spec = connection_argument_spec()
    argument_spec.update(
        title=dict(type="str", required=True),
        description=dict(type="str", default=""),
        monitors=dict(type="list", elements="str"),
        status_pages=dict(type="list", elements="str"),
        all_status_pages=dict(type="bool", default=False),
        duration_minutes=dict(type="int", default=60),
        state=dict(
            type="str",
            choices=["present", "paused", "absent"],
            default="present",
        ),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if socketio is None:
        module.fail_json(
            msg=missing_required_lib("python-socketio"),
            exception=SOCKETIO_IMPORT_ERROR,
        )

    client = UptimeKumaClient(
        module.params["api_url"], timeout=module.params["api_timeout"]
    )
    try:
        client.connect()
        result = run(module, client)
    except UptimeKumaError as exc:
        module.fail_json(msg=str(exc))
    finally:
        client.disconnect()

    module.exit_json(**result)


if __name__ == "__main__":
    main()
