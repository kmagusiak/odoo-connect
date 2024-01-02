import math
from datetime import date, datetime

import pytest

import odoo_connect.format as odoo_format


def test_binary_encoding():
    bin = b'OK'
    value = odoo_format.format_binary(bin)
    assert isinstance(value, str)
    assert len(value) == math.ceil(len(bin) / 3) * 4

    original = odoo_format.decode_binary(value)
    assert isinstance(original, bytes) and original == bin


@pytest.mark.parametrize(
    "type_name,input,expected",
    [
        ('char', 'test', 'test'),
        ('integer', 3, 3),
        ('date', datetime(2020, 2, 2, 3), "2020-02-02"),
        ('date', date(2020, 2, 2), "2020-02-02"),
        ('date', None, False),
        ('datetime', datetime(2020, 2, 2, 3, microsecond=3), "2020-02-02 03:00:00"),
        ('datetime', "2020-02-02 03:00:00.3", "2020-02-02 03:00:00"),
        ('datetime', date(2020, 2, 2), "2020-02-02 00:00:00"),
        ('datetime', None, False),
        ('binary', b'', ''),
        ('char', '', False),
        ('char', None, False),
        ('boolean', False, False),
        ('integer', False, 0),
    ],
)
def test_format(type_name, input, expected):
    ff = odoo_format._FORMAT_FUNCTIONS.get(type_name)
    formatter = ff[0] if ff else odoo_format.format_default
    assert formatter(input) == expected, "Couldn't format %s" % type_name


@pytest.mark.parametrize(
    "type_name,input,expected",
    [
        ('char', 'test', 'test'),
        ('int', 3, 3),
        ('date', "2022-02-02", date(2022, 2, 2)),
        ('date', False, None),
        ('datetime', "2020-02-02 03:00:00", datetime(2020, 2, 2, 3)),
        ('binary', '', b''),
        ('char', False, None),
        ('boolean', False, False),
        ('json', "{'a': 1}", {'a': 1}),
    ],
)
def test_decode(type_name, input, expected):
    ff = odoo_format._FORMAT_FUNCTIONS.get(type_name)
    decoder = ff[1] if ff else odoo_format.decode_default
    assert decoder(input) == expected, "Couldn't decode %s" % type_name


def test_formatter():
    f = odoo_format.Formatter()
    f.format_function['d'] = odoo_format.format_date
    f.field_map['X'] = 'y'
    f.field_map['removed'] = ''
    assert f.map_field_name('X') == 'y'
    d = f.format_dict({'d': '2022-01-01 15:10:05', 'X': 'value y', 'def': 'ok ', 'removed': 1})
    print(d)
    assert d['d'] == '2022-01-01'
    assert 'X' not in d and d['y'] == 'value y'
    assert d['def'] == 'ok'
    assert 'removed' not in d


def test_decoder():
    f = odoo_format.Formatter()
    f.decode_function['d'] = odoo_format.decode_date
    d = f.decode_dict({'d': '2022-01-01', 'x': '2022-01-01'})
    print(d)
    assert d['d'] == date(2022, 1, 1)
    assert d['x'] == '2022-01-01'


def test_formatter_lower_case():
    f = odoo_format.Formatter(lower_case_fields=True)
    assert f.map_field_name('OK') == 'ok'


def test_formatter_ignored_fields():
    f = odoo_format.Formatter()
    assert f.format_dict({'write_uid': 5, 'a': 1}) == {'a': 1}
