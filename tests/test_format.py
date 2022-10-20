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


def test_binary_encoding_empty():
    assert odoo_format.format_binary(b'') == ''


@pytest.mark.parametrize(
    "type_name,func,input,expected",
    [
        ('char', 'default', 'test', 'test'),
        ('int', 'default', 3, 3),
        ('date', 'date', datetime(2020, 2, 2, 3), "2020-02-02"),
        ('date', 'date', date(2020, 2, 2), "2020-02-02"),
        ('date', 'date', None, False),
        ('datetime', 'datetime', datetime(2020, 2, 2, 3, microsecond=3), "2020-02-02 03:00:00"),
        ('datetime', 'datetime', "2020-02-02 03:00:00.3", "2020-02-02 03:00:00"),
        ('datetime', 'datetime', date(2020, 2, 2), "2020-02-02 00:00:00"),
        ('datetime', 'datetime', None, False),
        ('binary', 'binary', b'', ''),
        ('char', 'default', '', False),
    ],
)
def test_format(type_name, func, input, expected):
    formatter = getattr(odoo_format, "format_%s" % func)
    assert formatter(input) == expected, "Couldn't format %s" % type_name


@pytest.mark.parametrize(
    "type_name,func,input,expected",
    [
        ('char', 'default', 'test', 'test'),
        ('int', 'default', 3, 3),
        ('date', 'date', "2022-02-02", date(2022, 2, 2)),
        ('date', 'date', False, None),
        ('datetime', 'datetime', "2020-02-02 03:00:00", datetime(2020, 2, 2, 3)),
        ('binary', 'binary', '', b''),
    ],
)
def test_decode(type_name, func, input, expected):
    decoder = getattr(odoo_format, "decode_%s" % func)
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
