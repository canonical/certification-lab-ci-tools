#!/usr/bin/env python3

"""
Stack a sequence of Checkbox configuration files

Example:
```
stacker \
--output stacked.conf \
--description "A simple Checkbox configuration file" \
launcher.conf manifest.conf
```
"""

from argparse import ArgumentParser
from pathlib import Path

from launcher.configuration import CheckBoxConfiguration


def parse_arguments():
    parser = ArgumentParser(description="Stack Checkbox configuration files.")
    parser.add_argument(
        "config_files", nargs="+", type=Path, help="Configuration file to be stacked"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="The resulting stacked configuration file",
        required=True,
    )
    parser.add_argument(
        "--description",
        type=str,
        help="Description for the resulting stacked configuration file",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    CheckBoxConfiguration().stack(
        paths=args.config_files, output=args.output, description=args.description
    )


if __name__ == "__main__":
    main()
