#!/usr/bin/env python3
# Copyright (c) 2020 Canonical Ltd.
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

"""Push measurements stored in JSON file to InfluxDB."""

import json

from argparse import ArgumentParser
from influxdb import InfluxDBClient


def isanyinstance(obj, types):
    """Check if `obj` is an instance of any of the `types`."""
    return any([isinstance(obj, t) for t in types])


def validate_point(data_point):
    """
    Check if the data_point is in valid format as accepted by the
    InfluxDB Python client.

    :param data_point:
        a dict containing data point information
    :returns:
        a list of problems with the data point
        (empty list on everything being ok)
    """
    if not isinstance(data_point, dict):
        return ["Data point {} is not a dict".format(data_point)]
    mandatory = {
        "measurement": [str],
        "fields": [dict],
    }
    optional = {
        "tags": [dict],
        "time": [int, str],
    }
    errors = []
    for name, types in mandatory.items():
        if name not in data_point.keys():
            errors.append(
                "Problem with data point: {}. '{}' field missing".format(
                    data_point, name
                )
            )
            continue
        if not isanyinstance(data_point[name], types):
            errors.append(
                "Problem with data point: {}. '{}' is not a type of {}".format(
                    data_point, name, types
                )
            )
    for name, types in optional.items():
        if name in data_point.keys():
            if not isanyinstance(data_point[name], types):
                errors.append(
                    "Problem with data point: {}. '{}' is not a type of {}".format(
                        data_point, name, types
                    )
                )
    return errors


def main():
    """Entry point."""
    parser = ArgumentParser()
    parser.add_argument("--host", help="Influx host ot push to", required=True)
    parser.add_argument(
        "--username", "-u", help="Username for the Influx client", required=True
    )
    parser.add_argument(
        "--password", "-p", help="Password for the Influx client", required=True
    )
    parser.add_argument("--database", "-d", help="Database to use", required=True)
    parser.add_argument(
        "measurements", help="JSON file with the measurements", metavar="file.json"
    )
    args = parser.parse_args()
    # look for the port in the --host option
    split = args.host.split(":")
    host = split[0]
    port = 8086 if len(split) == 1 else int(split[1])
    errors = []
    try:
        with open(args.measurements, "rt") as measurements_file:
            data = json.load(measurements_file)
            # if there's only one object we need to listify it
            datapoints = data if isinstance(data, list) else [data]
            for datapoint in datapoints:
                errors += validate_point(datapoint)
    except json.JSONDecodeError as exc:
        errors.append("JSON decode error: {}".format(str(exc)))
    if errors:
        raise SystemExit("\n".join(errors))

    try:
        client = InfluxDBClient(host, port, args.username, args.password)
        client.write_points(datapoints, database=args.database)
    except Exception as exc:
        raise SystemExit("Problem with pushing the data: {}".format(exc))


if __name__ == "__main__":
    main()
