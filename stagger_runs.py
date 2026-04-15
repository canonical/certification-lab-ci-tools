#!/usr/bin/env python3
import os
import textwrap
import argparse
import time
import random
import itertools


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("minutes", type=int)
    return parser.parse_args()


def pretty_m_s(seconds):
    minutes = seconds // 60
    if minutes == 0:
        return "{} seconds".format(seconds)
    return "{} minutes".format(minutes)


def main():
    args = parse_args()
    sleeping_s = args.minutes * 60
    sleeping_s = random.randint(0, sleeping_s)
    # lets be flexible here because jenkins may set this envvar to false or 0
    if os.getenv("NO_STAGGER", "false").lower() in ["1", "true"]:
        print("NO_STAGGER is defined, skipping staggering")
        return

    pretty_deadline = pretty_m_s(sleeping_s)

    print(textwrap.dedent("""
    Staggering this run out to lower pressure on the lab network.
    This test run will start in {}.

    Will now print a spinner to avoid Output Timeout!
    You want to skip this?
    - Restart the job with NO_STAGGER envvar
    - Kill this process, my pid is: {}
    """.format(pretty_deadline, os.getpid())).strip())
    print(flush=True)

    spinner = itertools.cycle(r"-\|/")
    deadline = time.time() + sleeping_s
    while time.time() < deadline:
        print(next(spinner), end="\r", flush=True)
        time.sleep(min(10, deadline - time.time()))
    print("   ", end="\r")


if __name__ == "__main__":
    main()
