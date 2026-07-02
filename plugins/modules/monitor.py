#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: monitor
short_description: Manage Uptime Kuma monitors
description:
  - Create, update or delete an Uptime Kuma monitor over the Socket.IO API.
  - The monitor is identified by its exact I(name).
  - Common options are exposed directly; anything else (type-specific fields) can
    be passed through the free-form I(settings) dict.
  - Idempotency only considers the fields you actually set (plus the universal
    ones with defaults), so a monitor created elsewhere is only changed on those.
  - Targets Uptime Kuma 2.x.
author:
  - MrMegaNova (@MrMegaNova)
extends_documentation_fragment:
  - mrmeganova.uptime_kuma.connection
options:
  name:
    description: Exact name of the monitor.
    type: str
    required: true
  type:
    description:
      - Monitor type (for example V(http), V(ping), V(tcp), V(dns), V(keyword)).
      - Required when O(state=present).
    type: str
  url:
    description: Target URL (for HTTP-like monitors).
    type: str
  hostname:
    description: Target hostname (for ping/tcp/dns monitors).
    type: str
  port:
    description: Target port (for tcp-like monitors).
    type: int
  method:
    description: HTTP method (for HTTP monitors).
    type: str
  interval:
    description: Check interval, in seconds.
    type: int
    default: 60
  retry_interval:
    description: Retry interval, in seconds.
    type: int
    default: 60
  retries:
    description: Number of retries before the monitor is considered down.
    type: int
    default: 0
  upside_down:
    description: Invert the monitor result (up becomes down and vice versa).
    type: bool
    default: false
  active:
    description: Whether the monitor is running.
    type: bool
    default: true
  notifications:
    description:
      - Notification names (exact match) attached to the monitor.
      - When omitted, the current notification assignment is left untouched.
    type: list
    elements: str
  settings:
    description:
      - Extra type-specific fields sent verbatim (for example V(keyword),
        V(dns_resolve_type), V(headers)), overriding any of the above.
    type: dict
    default: {}
  delete_children:
    description: When deleting a group monitor, also delete its children.
    type: bool
    default: false
  state:
    description:
      - V(present) creates the monitor if missing, or updates it.
      - V(absent) deletes the monitor.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Ensure an HTTP monitor exists
  mrmeganova.uptime_kuma.monitor:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: srv-01 http
    type: http
    url: https://srv-01.example.org/health
    interval: 30
    notifications:
      - ops-webhook
  delegate_to: localhost

- name: A keyword monitor via settings
  mrmeganova.uptime_kuma.monitor:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: srv-01 keyword
    type: keyword
    url: https://srv-01.example.org
    settings:
      keyword: healthy
  delegate_to: localhost

- name: Remove a monitor
  mrmeganova.uptime_kuma.monitor:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: srv-01 http
    state: absent
  delegate_to: localhost
"""

RETURN = r"""
monitor_id:
  description: Id of the monitor, if it exists.
  type: int
  returned: success
  sample: 5
actions:
  description: Actions performed (or that would be performed in check mode).
  type: list
  elements: str
  returned: success
  sample: [created]
"""

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.mrmeganova.uptime_kuma.plugins.module_utils.uptime_kuma import (
    SOCKETIO_IMPORT_ERROR,
    UptimeKumaClient,
    UptimeKumaError,
    connection_argument_spec,
    socketio,
)

# Optional, type-specific options mapped to their server key.
OPTIONAL_KEYS = {
    "url": "url",
    "hostname": "hostname",
    "port": "port",
    "method": "method",
}


def resolve_notification_ids(client, names):
    """Map notification names to ids, failing on unknown names."""
    by_name = {n.get("name"): n for n in client.get_notifications()}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise UptimeKumaError(
            "Unknown notification(s): %s. Available: %s"
            % (", ".join(missing), ", ".join(sorted(k for k in by_name if k)))
        )
    return [by_name[n]["id"] for n in names]


def managed_fields(client, params):
    """Fields this run manages: universal ones plus whatever the user set."""
    fields = {
        "interval": params["interval"],
        "retryInterval": params["retry_interval"],
        "maxretries": params["retries"],
        "active": params["active"],
        "upsideDown": params["upside_down"],
    }
    for option, key in OPTIONAL_KEYS.items():
        if params[option] is not None:
            fields[key] = params[option]
    fields.update(params["settings"])
    return fields


def notif_ids_set(notification_id_list):
    """Normalize a notificationIDList dict to a set of int ids."""
    return {
        int(key)
        for key, enabled in (notification_id_list or {}).items()
        if enabled
    }


def run(module, client):
    params = module.params
    result = {"changed": False, "actions": [], "monitor_id": None}

    client.login(
        params["api_username"], params["api_password"], params["api_mfa_token"]
    )

    existing = None
    for monitor in client.get_monitors().values():
        if monitor.get("name") == params["name"]:
            existing = monitor
            result["monitor_id"] = monitor["id"]
            break

    if params["state"] == "absent":
        if existing:
            result["changed"] = True
            result["actions"].append("deleted")
            if not module.check_mode:
                client.delete_monitor(existing["id"], params["delete_children"])
        return result

    if not params["type"]:
        raise UptimeKumaError("type is required when state=present")

    fields = managed_fields(client, params)

    desired_notifs = None
    if params["notifications"] is not None:
        desired_notifs = {
            str(nid): True
            for nid in resolve_notification_ids(client, params["notifications"])
        }

    if not existing:
        result["changed"] = True
        result["actions"].append("created")
        if not module.check_mode:
            payload = {
                "type": params["type"],
                "name": params["name"],
                "method": params["method"] or "GET",
                "resendInterval": 0,
                "accepted_statuscodes": ["200-299"],
                "conditions": [],
                "notificationIDList": desired_notifs or {},
            }
            payload.update(fields)
            result["monitor_id"] = client.add_monitor(payload)
        return result

    # Existing: start from the full current monitor, apply the managed fields.
    current = client.get_monitor(existing["id"])
    changed_fields = any(current.get(key) != value for key, value in fields.items())
    changed_type = current.get("type") != params["type"]
    changed_notifs = (
        desired_notifs is not None
        and notif_ids_set(desired_notifs) != notif_ids_set(current.get("notificationIDList"))
    )

    if changed_fields or changed_type or changed_notifs:
        result["changed"] = True
        result["actions"].append("updated")
        if not module.check_mode:
            payload = dict(current)
            payload["type"] = params["type"]
            payload.update(fields)
            if desired_notifs is not None:
                payload["notificationIDList"] = desired_notifs
            client.edit_monitor(payload)

    return result


def main():
    argument_spec = connection_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        type=dict(type="str"),
        url=dict(type="str"),
        hostname=dict(type="str"),
        port=dict(type="int"),
        method=dict(type="str"),
        interval=dict(type="int", default=60),
        retry_interval=dict(type="int", default=60),
        retries=dict(type="int", default=0),
        upside_down=dict(type="bool", default=False),
        active=dict(type="bool", default=True),
        notifications=dict(type="list", elements="str"),
        settings=dict(type="dict", default={}),
        delete_children=dict(type="bool", default=False),
        state=dict(type="str", choices=["present", "absent"], default="present"),
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
