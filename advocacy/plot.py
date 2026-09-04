#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Sylvain Pineau <sylvain.pineau@canonical.com>

import argparse
import io
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests


def get_csv(filename=None):
    if filename:
        return filename
    url = "http://10.50.124.12:8086/query"
    h = {
        "Accept": "application/csv",
    }
    params = {"db": "desktopsnaps", "q": "SELECT * FROM startup_time"}
    a = requests.auth.HTTPBasicAuth("ce", os.getenv("INFLUX_PASS"))
    r = requests.post(url, headers=h, params=params, auth=a)
    return io.StringIO(r.text)


def plot(args):
    config = {"displaylogo": False}
    template = "%{y:.2f} s <b>%{customdata[0]} %{customdata[1]}"
    df = pd.read_csv(
        get_csv(args.csv),
        parse_dates={"date": ["time"]},
        date_parser=lambda time: pd.to_datetime(int(time)),
    )
    snaps = sorted(set(df["snap"]))
    prefix = "snap_baseline"
    triggers = ["linux-generic", "snapd", "core18", "apparmor", "libc6"]
    if args.os_baseline:
        prefix = "os_baseline"
        triggers = snaps
    ymax = df[(df["hw_id"] == args.hw_id) & (df["cause"].isin(triggers))]["cold"].max()
    include_js = True

    with open(f"{args.folder}/{prefix}_{args.hw_id}.html", "w") as f:
        for snap in snaps:
            data = df[
                (df["snap"] == snap)
                & (df["hw_id"] == args.hw_id)
                & (df["cause"].isin(triggers))
            ]
            releases = sorted(set(data["release"]))
            fig = go.Figure(layout_title_text=f"<b>{snap}")
            # Create traces
            for start in ["cold", "hot"]:
                for release in releases:
                    release_data = data[(data["release"] == release)]
                    fig.add_trace(
                        go.Scatter(
                            x=release_data["date"],
                            y=release_data[start],
                            mode="lines+markers",
                            xhoverformat="%Y-%m-%d %H:%M:%S",
                            customdata=np.stack(
                                (release_data["cause"], release_data["cause_version"]),
                                axis=-1,
                            ),
                            hovertemplate=template,
                            name=f"{start} start ({release})",
                        )
                    )
            fig.update_yaxes(range=[0, ymax + 1])
            fig.update_layout(
                margin=dict(l=80, r=100, t=80, b=20),
                height=500,
                hovermode="x unified",
                hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font={"color": "white"}),
                yaxis={"tickformat": ".2f"},
                xaxis=dict(
                    rangeselector=dict(
                        buttons=list(
                            [
                                dict(
                                    count=6,
                                    label="6m",
                                    step="month",
                                    stepmode="backward",
                                ),
                                dict(
                                    count=1, label="YTD", step="year", stepmode="todate"
                                ),
                                dict(
                                    count=1,
                                    label="1y",
                                    step="year",
                                    stepmode="backward",
                                ),
                                dict(step="all"),
                            ]
                        )
                    ),
                    type="date",
                ),
            )
            f.write(
                fig.to_html(full_html=False, config=config, include_plotlyjs=include_js)
            )
            include_js = False
            headers = [f"<b>{snap.capitalize()}<br>startup time"]
            values = [["Mean", "Std Dev", "Last"]]
            for release in releases:
                release_data = data[(data["release"] == release)]
                headers.append(f"<b>{release.capitalize()}<br>Cold / Hot (s)")
                values.append(
                    [
                        f"{release_data['cold'].mean():.2f}"
                        f" / {release_data['hot'].mean():.2f}",
                        f"{release_data['cold'].std():.2f}"
                        f" / {release_data['hot'].std():.2f}",
                        f"{release_data['cold'].iloc[-1]:.2f}"
                        f" / {release_data['hot'].iloc[-1]:.2f}",
                    ]
                )
            fig = go.Figure(
                data=[go.Table(header=dict(values=headers), cells=dict(values=values))]
            )
            fig.update_layout(margin=dict(l=80, r=200, t=20, b=20), height=155)
            f.write(
                fig.to_html(full_html=False, config=config, include_plotlyjs=include_js)
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hw_id", type=str, help="system tag")
    parser.add_argument("--folder", default="/tmp", help="Folder path to save reports")
    parser.add_argument("--os-baseline", action="store_true", help="OS baseline")
    parser.add_argument("--snap-baseline", action="store_true", help="Snap baseline")
    parser.add_argument("--csv", help="CSV influxdb export (optional)")
    args = parser.parse_args()
    plot(args)


if __name__ == "__main__":
    main()
