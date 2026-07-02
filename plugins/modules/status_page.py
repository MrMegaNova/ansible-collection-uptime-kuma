#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: status_page
short_description: Manage Uptime Kuma status pages
description:
  - Create, update or delete an Uptime Kuma status page over the Socket.IO API.
  - The status page is identified by its I(slug).
  - Optionally manages the monitors shown on the page, as a single public group.
  - Targets Uptime Kuma 2.x.
author:
  - MrMegaNova (@MrMegaNova)
extends_documentation_fragment:
  - mrmeganova.uptime_kuma.connection
options:
  slug:
    description: Slug of the status page (its URL path).
    type: str
    required: true
  title:
    description: Title of the status page.
    type: str
  description:
    description: Description shown on the status page.
    type: str
  theme:
    description: Colour theme of the status page.
    type: str
    choices: [auto, light, dark]
  show_tags:
    description: Whether to show monitor tags on the page.
    type: bool
  show_powered_by:
    description: Whether to show the "Powered by Uptime Kuma" footer.
    type: bool
  footer_text:
    description: Custom footer text.
    type: str
  monitors:
    description:
      - Monitor names (exact match) to display on the page, as a single group.
      - When omitted, the current monitor layout is left untouched.
    type: list
    elements: str
  monitors_group:
    description: Name of the group holding I(monitors).
    type: str
    default: Services
  state:
    description:
      - V(present) creates the status page if missing, or updates it.
      - V(absent) deletes the status page.
    type: str
    choices: [present, absent]
    default: present
notes:
  - The C(published) flag cannot be toggled through the Uptime Kuma 2.x API
    (the server ignores it on save), so this module does not manage it.
"""

EXAMPLES = r"""
- name: Ensure a public status page exists
  mrmeganova.uptime_kuma.status_page:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    slug: public
    title: Public status
    theme: auto
    monitors:
      - srv-01 http
      - srv-01 ping
  delegate_to: localhost

- name: Remove the status page
  mrmeganova.uptime_kuma.status_page:
    api_url: https://status.example.org
    api_username: admin
    api_password: "{{ vault_kuma_password }}"
    slug: public
    state: absent
  delegate_to: localhost
"""

RETURN = r"""
slug:
  description: Slug of the status page.
  type: str
  returned: success
  sample: public
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

# Module option -> status page config key.
CONFIG_KEYS = {
    "title": "title",
    "description": "description",
    "theme": "theme",
    "show_tags": "showTags",
    "show_powered_by": "showPoweredBy",
    "footer_text": "footerText",
}


def resolve_monitor_ids(client, names):
    """Map monitor names to ids, failing on unknown or ambiguous names."""
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
    return [by_name[n][0]["id"] for n in names]


def apply_overrides(config, params):
    """Return config with the user-provided fields applied."""
    config = dict(config)
    for option, key in CONFIG_KEYS.items():
        if params[option] is not None:
            config[key] = params[option]
    return config


def groups_signature(group_list):
    """Comparable view of a publicGroupList: [(name, [monitor_id, ...]), ...]."""
    return [
        (g.get("name"), [m.get("id") for m in g.get("monitorList", [])])
        for g in group_list
    ]


def desired_groups(client, params, current_groups):
    """Groups to persist: a single group from I(monitors), or the current ones."""
    if params["monitors"] is None:
        return current_groups
    ids = resolve_monitor_ids(client, params["monitors"])
    return [
        {
            "name": params["monitors_group"],
            "monitorList": [{"id": mid} for mid in ids],
        }
    ]


def run(module, client):
    params = module.params
    slug = params["slug"]
    result = {"changed": False, "actions": [], "slug": slug}

    client.login(
        params["api_username"], params["api_password"], params["api_mfa_token"]
    )

    exists = any(p.get("slug") == slug for p in client.get_status_pages())

    if params["state"] == "absent":
        if exists:
            result["changed"] = True
            result["actions"].append("deleted")
            result["diff"] = {"before": {"slug": slug}, "after": {}}
            if not module.check_mode:
                client.delete_status_page(slug)
        return result

    if not exists:
        after = {"slug": slug}
        for option in CONFIG_KEYS:
            if params[option] is not None:
                after[option] = params[option]
        if params["monitors"] is not None:
            after["monitors"] = params["monitors"]
        result["changed"] = True
        result["actions"].append("created")
        result["diff"] = {"before": {}, "after": after}
        if not module.check_mode:
            client.add_status_page(params["title"] or slug, slug)
            config = apply_overrides(client.get_status_page(slug)["config"], params)
            groups = desired_groups(client, params, [])
            client.save_status_page(slug, config, config.get("icon"), groups)
        return result

    # Existing: diff config and monitor groups, save only if something changed.
    config = client.get_status_page(slug)["config"]
    public = client.get_status_page_public(slug)
    current_groups = public.get("publicGroupList", [])

    new_config = apply_overrides(config, params)
    new_groups = desired_groups(client, params, current_groups)

    config_changed = any(
        new_config.get(key) != config.get(key) for key in CONFIG_KEYS.values()
    )
    groups_changed = groups_signature(new_groups) != groups_signature(current_groups)

    if config_changed or groups_changed:
        result["changed"] = True
        result["actions"].append("updated")
        before = {"slug": slug}
        after = {"slug": slug}
        for option, key in CONFIG_KEYS.items():
            if params[option] is not None:
                before[option] = config.get(key)
                after[option] = new_config.get(key)
        if params["monitors"] is not None:
            before["monitors"] = groups_signature(current_groups)
            after["monitors"] = groups_signature(new_groups)
        result["diff"] = {"before": before, "after": after}
        if not module.check_mode:
            client.save_status_page(
                slug, new_config, new_config.get("icon"), new_groups
            )

    return result


def main():
    argument_spec = connection_argument_spec()
    argument_spec.update(
        slug=dict(type="str", required=True),
        title=dict(type="str"),
        description=dict(type="str"),
        theme=dict(type="str", choices=["auto", "light", "dark"]),
        show_tags=dict(type="bool"),
        show_powered_by=dict(type="bool"),
        footer_text=dict(type="str"),
        monitors=dict(type="list", elements="str"),
        monitors_group=dict(type="str", default="Services"),
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
