#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: info
short_description: Read Uptime Kuma resources
description:
  - Gather Uptime Kuma resources (monitors, status pages, notifications, tags,
    maintenance windows) over the Socket.IO API.
  - This module is read-only; it never reports a change and runs unchanged in
    check mode.
  - Targets Uptime Kuma 2.x.
author:
  - MrMegaNova (@MrMegaNova)
extends_documentation_fragment:
  - mrmeganova.uptime_kuma.connection
options:
  gather:
    description: Which resources to return.
    type: list
    elements: str
    choices: [monitors, status_pages, notifications, tags, maintenances]
    default: [monitors, status_pages, notifications, tags, maintenances]
"""

EXAMPLES = r"""
- name: Gather everything
  mrmeganova.uptime_kuma.info:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
  delegate_to: localhost
  register: kuma

- name: Only monitors and tags
  mrmeganova.uptime_kuma.info:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    gather: [monitors, tags]
  delegate_to: localhost
  register: kuma
"""

RETURN = r"""
monitors:
  description: Monitors, when requested.
  type: list
  elements: dict
  returned: when I(monitors) is gathered
status_pages:
  description: Status pages, when requested.
  type: list
  elements: dict
  returned: when I(status_pages) is gathered
notifications:
  description: Notifications, when requested.
  type: list
  elements: dict
  returned: when I(notifications) is gathered
tags:
  description: Tags, when requested.
  type: list
  elements: dict
  returned: when I(tags) is gathered
maintenances:
  description: Maintenance windows, when requested.
  type: list
  elements: dict
  returned: when I(maintenances) is gathered
"""

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.mrmeganova.uptime_kuma.plugins.module_utils.uptime_kuma import (
    SOCKETIO_IMPORT_ERROR,
    UptimeKumaClient,
    UptimeKumaError,
    connection_argument_spec,
    socketio,
)


def run(module, client):
    params = module.params
    result = {"changed": False}

    client.login(
        params["api_username"], params["api_password"], params["api_mfa_token"]
    )

    gatherers = {
        "monitors": lambda: list(client.get_monitors().values()),
        "status_pages": client.get_status_pages,
        "notifications": client.get_notifications,
        "tags": client.get_tags,
        "maintenances": client.get_maintenances,
    }
    for resource in params["gather"]:
        result[resource] = gatherers[resource]()

    return result


def main():
    argument_spec = connection_argument_spec()
    argument_spec.update(
        gather=dict(
            type="list",
            elements="str",
            choices=[
                "monitors",
                "status_pages",
                "notifications",
                "tags",
                "maintenances",
            ],
            default=[
                "monitors",
                "status_pages",
                "notifications",
                "tags",
                "maintenances",
            ],
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
