import json

from flask import Flask, request
from influxdb import InfluxDBClient

from influx_credentials import credentials
from pprint import pprint


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
    if type(data_point) != dict:
        return ["Data point {} is not a dict".format(data_point)]
    RIGHT_TYPES = {
        "measurement": [str],
        "tags": [dict],
        "time": [int, str],
        "fields": [dict],
    }
    errors = []
    for name, types in RIGHT_TYPES.items():
        if name not in data_point.keys():
            errors.append(
                "Problem with data point: {}. '{}' field missing".format(
                    data_point, name
                )
            )
            continue
        if type(data_point[name]) not in types:
            errors.append(
                "Problem with data point: {}. '{}' is not a type of {}".format(
                    data_point, name, types
                )
            )
    return errors


def create_app(config_name=None):
    app = Flask(__name__)

    with app.app_context():
        if config_name == "testing":

            class MockDB:
                def write_points(*args, **kwargs):
                    return True

            app.influx_client = MockDB()
        else:
            app.influx_client = InfluxDBClient(
                credentials["host"], 8086, credentials["user"], credentials["pass"]
            )

    @app.route("/influx", methods=["POST"])
    def influx():
        if request.headers.get("Content-Type") != "application/json":
            return ("Not json!", 400)
        try:
            payload = json.loads(request.data.decode("utf-8"))
            pprint(payload)
            if "database" not in payload.keys():
                return ("No database specified", 400)
            dbname = payload["database"]
            measurements = payload["measurements"]
        except json.decoder.JSONDecodeError as exc:
            return ("JSON decode error: {}".format(exc), 400)
        err_msgs = []
        for point in measurements:
            err_msgs += validate_point(point)
        if err_msgs:
            return (", ".join(err_msgs), 400)
        try:
            query_res = app.influx_client.write_points(measurements, database=dbname)
        except Exception as exc:
            return ("Failed to write data point: {}".format(exc), 400)
        return "OK" if query_res else ("Failed to write data point", 400)

    return app


app = create_app()
