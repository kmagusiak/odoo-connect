import logging
import re

import pytest
import requests

import odoo_connect


@pytest.fixture(scope='session')
def connect_params():
    runbot_page = requests.get('https://runbot.odoo.com/')
    odoo_url = "http://localhost/"
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
            break
    odoo_url = odoo_url.replace('http://', 'https://')
    logging.info("Using odoo server %s: %s", version, odoo_url)

    return {
        'url': odoo_url,
        'username': 'admin',
        'password': 'admin',
    }


@pytest.fixture(scope='session')
def odoo_session(connect_params):
    return odoo_connect.connect(**connect_params)
