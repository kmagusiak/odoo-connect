import logging
import re

import pytest
import requests

import odoo_connect


@pytest.fixture(scope='session')
def connect_params():
    runbot_url = 'https://runbot.odoo.com/'
    runbot_page = requests.get(runbot_url)
    odoo_url = "http://localhost:8069/"
    version = "unknown"
    # we don't use (yet) any XML parsing to keep dependencies simple
    # find one of the following and select a URL
    # - bundle href (row and name of the branch)
    # - link to a sign-in action (avoid documentation and take only stable versions)
    for m in re.finditer(
        r'href="/runbot/(bundle)[^<]+<b>([^<]*)</b>'
        r'|<a class="[^"]*fa-(sign-in)[^"]*" href="([^"]*)"',
        runbot_page.text,
    ):
        if m.group(1) == 'bundle':
            version = m.group(2)
        elif (
            re.match(r'^\d+\.\d$', version)
            and m.group(3) == 'sign-in'
            and 'build/html' not in m.group(4)
        ):
            odoo_url = m.group(4)
            if odoo_url.startswith('/'):
                # relative path, will redirect to server, find it
                odoo_url = odoo_connect.odoo_rpc.urljoin(runbot_url, odoo_url)
                resp = requests.head(odoo_url)
                if resp.is_redirect:
                    odoo_url = resp.next.url
            else:
                odoo_url = odoo_url.replace('http://', 'https://')
            break
    logging.info("Using odoo server %s: %s", version, odoo_url)

    return {
        'url': odoo_url,
        'username': 'admin',
        'password': 'admin',
        'check_connection': False,
    }


@pytest.fixture(scope='session')
def odoo_session(connect_params):
    return odoo_connect.connect(**connect_params)
