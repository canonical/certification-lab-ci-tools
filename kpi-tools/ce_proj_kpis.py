#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2019 Canonical Ltd.
#
# Authors:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
This program computes KPIs of Customer Engineering projects
and posts measurements to the InfluxDB via Taipei Lab DB-bridge
"""

import time

from pprint import pprint

import pygsheets
import requests


def optional_int(string):
    """
    Try "extracting" integer from a string.
    Returns extracted integer or None if string couldn't be parsed.
    >>> optional_int('42')
    42
    >>> optional_int('-42')
    -42
    >>> optional_int('0')
    0
    >>> optional_int('')
    >>> optional_int('-')
    >>> optional_int('two')
    """
    try:
        return int(string)
    except ValueError:
        return None


def optional_percent(string):
    """
    Try "extracting" a percentage from a string.
    Returns a real number or None
    if string couldn't be parsed.
    >>> optional_percent('42.5%')
    0.425
    >>> optional_percent('1%')
    0.01
    >>> optional_percent('-42%')
    -0.42
    >>> optional_percent('42')
    >>> optional_percent('seven percent')
    >>> optional_percent('N/A')
    """
    try:
        if string[-1] != "%":
            return None
        # drop '%' suffix and divide by 100
        return float(string[:-1]) / 100.0
    except (ValueError, IndexError):
        return None


def currency(string):
    """
    >>> currency('42')
    42.0
    >>> currency('$42')
    42.0
    >>> currency('-100')
    -100.0
    >>> currency('$-100')
    -100.0
    >>> currency('$-10-10')
    >>> currency('$10,000')
    10000.0
    >>> currency('USD200')
    200.0
    >>> currency('$-10-10')
    >>>
    >>> currency('$-80.01')
    -80.01
    """
    filtered = ""
    for char in string:
        if char in "0123456789-.":
            filtered += char
    try:
        return float(filtered)
    except (ValueError, IndexError):
        return None


def get_prebaked_kpis():
    sheet_id = "11cbEwUsOCuv5Hs5RRh1VZZccZ-PDwA8rDdzbiyRkmUw"
    gcli = pygsheets.authorize()
    sheet = gcli.open_by_key(sheet_id)
    wsheet = sheet.worksheet_by_title("KPIs")
    all_vals = wsheet.get_all_values()
    kpis = dict()
    for row_num, row in enumerate(all_vals, start=1):
        if row[0].lower() in ["iot overall", "store overall", "pc overall"]:
            lob = row[0].split(" ")[0].lower()
            kpis["avg_{}_time_to_market".format(lob)] = optional_int(row[1]) or 0
            kpis["avg_{}_budget_variance".format(lob)] = optional_percent(row[2]) or 0
            kpis["avg_{}_scope_creep".format(lob)] = optional_int(row[3]) or 0
            kpis["avg_{}_nps".format(lob)] = optional_int(row[4]) or 0
            kpis["avg_{}_roi".format(lob)] = optional_percent(row[5]) or 0
    return kpis


def main():
    """Get stats and post measurements."""
    kpis = get_prebaked_kpis()
    print("Posting measuremens:")
    pprint(kpis)

    reqobj = {
        "database": "certsandbox",
        "measurements": [
            {
                "measurement": "project_kpis",
                "time": int(time.time() * 10**9),  # sec to nsec
                "tags": {},
                "fields": kpis,
            }
        ],
    }
    response = requests.post("http://10.101.51.246:8000/influx", json=reqobj)
    if not response.ok:
        raise SystemExit("Failed to post measurements:\n{}".format(response.text))


if __name__ == "__main__":
    main()
