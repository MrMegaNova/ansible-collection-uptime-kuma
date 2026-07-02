# -*- coding: utf-8 -*-
# Copyright: (c) 2026, MrMegaNova
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type


class ModuleDocFragment(object):
    # Connection options shared by every module of the collection.
    DOCUMENTATION = r"""
options:
  api_url:
    description: URL of the Uptime Kuma instance.
    type: str
    required: true
  api_username:
    description:
      - Username used to log in.
      - Uptime Kuma API keys only cover the Prometheus metrics endpoint and
        cannot be used with the Socket.IO API.
    type: str
    required: true
  api_password:
    description: Password used to log in.
    type: str
    required: true
  api_mfa_token:
    description: One-time 2FA token, if enabled on the account.
    type: str
    default: ""
  api_timeout:
    description: Connection and per-call timeout, in seconds.
    type: int
    default: 30
requirements:
  - python-socketio
  - websocket-client
"""
