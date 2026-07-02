#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: notification
short_description: Manage Uptime Kuma notifications
description:
  - Create, update or delete an Uptime Kuma notification over the Socket.IO API.
  - The notification is identified by its exact I(name).
  - Type-specific settings are passed as a free-form dict in I(settings), so any
    notification provider supported by the server can be configured without this
    module knowing its schema.
  - Targets Uptime Kuma 2.x.
author:
  - MrMegaNova (@MrMegaNova)
extends_documentation_fragment:
  - mrmeganova.uptime_kuma.connection
options:
  name:
    description: Exact name of the notification.
    type: str
    required: true
  type:
    description:
      - Provider type (for example V(telegram), V(webhook), V(smtp), V(discord)).
      - Required when O(state=present).
    type: str
  settings:
    description:
      - Provider-specific settings, as documented by Uptime Kuma for the chosen
        O(type) (for example V(webhookURL) for a webhook).
      - Keys are sent verbatim; secret values should be supplied through Ansible
        Vault.
    type: dict
    default: {}
  is_default:
    description: Whether the notification is applied to new monitors by default.
    type: bool
    default: false
  state:
    description:
      - V(present) creates the notification if missing, or updates it if its
        configuration differs.
      - V(absent) deletes the notification.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Ensure a webhook notification exists
  mrmeganova.uptime_kuma.notification:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: ops-webhook
    type: webhook
    settings:
      webhookURL: https://example.org/hook
      webhookContentType: json
  delegate_to: localhost

- name: Remove the notification
  mrmeganova.uptime_kuma.notification:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: ops-webhook
    state: absent
  delegate_to: localhost
"""

RETURN = r"""
notification_id:
  description: Id of the notification, if it exists.
  type: int
  returned: success
  sample: 2
actions:
  description: Actions performed (or that would be performed in check mode).
  type: list
  elements: str
  returned: success
  sample: [created]
"""

import json

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.mrmeganova.uptime_kuma.plugins.module_utils.uptime_kuma import (
    SOCKETIO_IMPORT_ERROR,
    UptimeKumaClient,
    UptimeKumaError,
    connection_argument_spec,
    socketio,
)


def build_notification(params):
    """Assemble the notification object sent to the server.

    Type-specific settings live at the top level next to name/type, mirroring
    what the Uptime Kuma front-end sends.
    """
    notification = dict(params["settings"])
    notification["name"] = params["name"]
    notification["type"] = params["type"]
    notification["isDefault"] = params["is_default"]
    return notification


def _normalize(config):
    """Drop keys the server rewrites so two configs can be compared."""
    config = dict(config)
    # applyExisting is a one-shot flag the server forces to false before storing.
    config.pop("applyExisting", None)
    return config


def run(module, client):
    params = module.params
    result = {"changed": False, "actions": [], "notification_id": None}

    client.login(
        params["api_username"], params["api_password"], params["api_mfa_token"]
    )

    existing = None
    for notification in client.get_notifications():
        if notification.get("name") == params["name"]:
            existing = notification
            result["notification_id"] = notification["id"]
            break

    if params["state"] == "absent":
        if existing:
            result["changed"] = True
            result["actions"].append("deleted")
            result["diff"] = {
                "before": _normalize(json.loads(existing.get("config") or "{}")),
                "after": {},
            }
            if not module.check_mode:
                client.delete_notification(existing["id"])
        return result

    if not params["type"]:
        raise UptimeKumaError("type is required when state=present")

    desired = build_notification(params)

    if not existing:
        result["changed"] = True
        result["actions"].append("created")
        result["diff"] = {"before": {}, "after": _normalize(desired)}
        if not module.check_mode:
            result["notification_id"] = client.add_notification(desired)
        return result

    # The stored config is the JSON we sent last time; compare it to the desired one.
    current = json.loads(existing.get("config") or "{}")
    if _normalize(current) != _normalize(desired):
        result["changed"] = True
        result["actions"].append("updated")
        result["diff"] = {
            "before": _normalize(current),
            "after": _normalize(desired),
        }
        if not module.check_mode:
            client.add_notification(desired, existing["id"])

    return result


def main():
    argument_spec = connection_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        type=dict(type="str"),
        settings=dict(type="dict", default={}),
        is_default=dict(type="bool", default=False),
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
