#!/usr/bin/env python3
import argparse
import re
import json
import lzma
import time
import string
import logging
import itertools
from pathlib import Path
from multiprocessing.pool import Pool
from urllib.error import HTTPError
from urllib.request import Request, urlopen

RETRY = 5
CACHE = Path.cwd() / ".cache"


def get_url(series, pocket, repo, arch) -> str:
    if arch.startswith("arm"):
        archive_url = "http://ports.ubuntu.com/ubuntu-ports/dists"
    else:
        archive_url = "http://tw.archive.ubuntu.com/ubuntu/dists"
    return f"{archive_url}/{series}-{pocket}/{repo}/binary-{arch}/Packages.xz"


def download_package_xz(url: str, cache_path: Path) -> Path:
    filename = "".join(x if x in string.ascii_letters else "_" for x in url)
    dest = cache_path / filename
    meta_path = dest.with_suffix(dest.suffix + ".meta")

    cache_path.mkdir(parents=True, exist_ok=True)

    headers = {}
    if dest.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if "etag" in meta:
            headers["If-None-Match"] = meta["etag"]
        if "last-modified" in meta:
            headers["If-Modified-Since"] = meta["last-modified"]

    req = Request(url, headers=headers)
    try:
        with urlopen(req) as resp:
            dest.write_bytes(resp.read())
            meta = {}
            if etag := resp.headers.get("ETag"):
                meta["etag"] = etag
            if last_modified := resp.headers.get("Last-Modified"):
                meta["last-modified"] = last_modified
            meta_path.write_text(json.dumps(meta))
    except HTTPError as e:
        if e.code == 304:
            logging.debug(f"Skipping download {url} as content didn't change")
            return dest
        raise

    return dest


def parse_package_name_version(package_spec: str) -> dict:
    pkg_name = re.search("Package: (.+)", package_spec)
    pkg_ver = re.search("Version: (.+)", package_spec)
    if pkg_name and pkg_ver:
        # Periods in json keys are bad, convert them to _
        pkg_name_key = pkg_name.group(1).replace(".", "_")
        return (pkg_name_key, pkg_ver.group(1))


def parse_package_xz(path: Path) -> dict:
    with lzma.open(path) as f:
        packages = f.read()
    packages = packages.decode("utf-8", errors="ignore").split("\n\n")
    packages = [parse_package_name_version(x) for x in packages if x]
    return {
        package_name: package_version
        for (package_name, package_version) in filter(bool, packages)
    }


def download_package_info_preserve(series_pocket_repo_arch) -> Path:
    series, pocket, repo, arch = series_pocket_repo_arch
    # If the JSON data already exists, read it so we can update it because
    # we want to preserve the latest seen version of each package even if
    # it's not in the Packages data because it migrated out of proposed
    save_to = Path(f"{series}-{repo}-{arch}-{pocket}.json")
    to_save = {}
    try:
        with save_to.open("r") as f:
            to_save = json.load(f) or {}
    except FileNotFoundError:
        pass

    url = get_url(series, pocket, repo, arch)
    for i in range(0, RETRY):
        try:
            path = download_package_xz(url, CACHE)
            break
        except Exception as e:
            if i == RETRY - 1:
                raise
            print(f"Trying to download failed with error: {e}", flush=True)
            print(f"Sleeping for {10 * i}s")
            time.sleep(10 * i)

    new_results = parse_package_xz(path)
    to_save.update(new_results)
    with save_to.open("w+") as f:
        json.dump(to_save, f)
    return save_to


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download and parse Ubuntu package data"
    )
    parser.add_argument(
        "--series", required=True, nargs="+", help="Ubuntu series (e.g. jammy)"
    )
    parser.add_argument(
        "--pocket", required=True, nargs="+", help="Pocket (e.g. proposed)"
    )
    parser.add_argument(
        "--repo", nargs="+", required=True, help="Repository (e.g. main)"
    )
    parser.add_argument(
        "--arch", required=True, nargs="+", help="Architecture (e.g. amd64)"
    )
    parser.add_argument(
        "--sequential",
        help="Download sequentially to make debugging easier",
        action="store_true",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    series, pocket, repo, arch = args.series, args.pocket, args.repo, args.arch

    tot = len(series) * len(pocket) * len(repo) * len(arch)
    to_do = itertools.product(series, pocket, repo, arch)

    if args.sequential:
        res_path = map(download_package_info_preserve, to_do)
        for i, v in enumerate(res_path, 1):
            print(f"Done [{i}/{tot}]: {v}", flush=True)
    else:
        with Pool() as p:
            res_path = p.imap_unordered(download_package_info_preserve, to_do)
            for i, v in enumerate(res_path, 1):
                print(f"Done [{i}/{tot}]: {v}", flush=True)


if __name__ == "__main__":
    main()
