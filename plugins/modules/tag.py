#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: tag
short_description: Manage Uptime Kuma tags
description:
  - Create, update or delete an Uptime Kuma tag over the Socket.IO API.
  - The tag is identified by its exact I(name).
  - Targets Uptime Kuma 2.x.
author:
  - MrMegaNova (@MrMegaNova)
extends_documentation_fragment:
  - mrmeganova.uptime_kuma.connection
options:
  name:
    description: Exact name of the tag.
    type: str
    required: true
  color:
    description:
      - Colour of the tag, as a CSS hex string (for example V(#059669)).
      - When omitted, a new tag is created with Uptime Kuma's default colour and
        an existing tag keeps its current colour.
    type: str
  state:
    description:
      - V(present) creates the tag if missing, or updates its colour if it exists.
      - V(absent) deletes the tag.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Ensure a "production" tag exists
  mrmeganova.uptime_kuma.tag:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: production
    color: "#059669"
  delegate_to: localhost

- name: Remove the tag
  mrmeganova.uptime_kuma.tag:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    name: production
    state: absent
  delegate_to: localhost
"""

RETURN = r"""
tag_id:
  description: Id of the tag, if it exists.
  type: int
  returned: success
  sample: 4
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

# Uptime Kuma's default colour for a new tag.
DEFAULT_COLOR = "#059669"


def run(module, client):
    params = module.params
    result = {"changed": False, "actions": [], "tag_id": None}

    client.login(
        params["api_username"], params["api_password"], params["api_mfa_token"]
    )

    existing = None
    for tag in client.get_tags():
        if tag.get("name") == params["name"]:
            existing = tag
            result["tag_id"] = tag["id"]
            break

    if params["state"] == "absent":
        if existing:
            result["changed"] = True
            result["actions"].append("deleted")
            result["diff"] = {
                "before": {"name": existing["name"], "color": existing.get("color")},
                "after": {},
            }
            if not module.check_mode:
                client.delete_tag(existing["id"])
        return result

    if not existing:
        color = params["color"] or DEFAULT_COLOR
        result["changed"] = True
        result["actions"].append("created")
        result["diff"] = {
            "before": {},
            "after": {"name": params["name"], "color": color},
        }
        if not module.check_mode:
            tag = client.add_tag({"name": params["name"], "color": color})
            result["tag_id"] = tag["id"]
        return result

    # Tag exists: only the colour can change, and only if explicitly requested.
    if params["color"] is not None and existing.get("color") != params["color"]:
        result["changed"] = True
        result["actions"].append("updated")
        result["diff"] = {
            "before": {"name": params["name"], "color": existing.get("color")},
            "after": {"name": params["name"], "color": params["color"]},
        }
        if not module.check_mode:
            client.edit_tag(
                {
                    "id": existing["id"],
                    "name": params["name"],
                    "color": params["color"],
                }
            )

    return result


def main():
    argument_spec = connection_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        color=dict(type="str"),
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
