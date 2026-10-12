#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only

"""Download prebuilts from ci.android.com."""

import argparse
import json
import os
import shutil
import socket
import sys
import urllib.error
import urllib.request
import os

_ARTIFACT_URL_FMT = "https://ci.android.com/builds/submitted/{build_id}/{build_target}/latest/raw/{filename}"

# ci.android.com might have issue with IPv6, try with IPv4 first
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_first_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return sorted(res, key=lambda r: r[0] != socket.AF_INET)


socket.getaddrinfo = _ipv4_first_getaddrinfo


class Downloader(object):
    def __init__(self, build_id, build_target):
        self.build_id = build_id
        self.build_target = build_target

    def _download_artifact(self, remote_filename, local_filename, mandatory=True):
        url = _ARTIFACT_URL_FMT.format(
            build_id=self.build_id,
            build_target=self.build_target,
            filename=urllib.parse.quote(remote_filename, safe=""),  # / -> %2F
        )
        local_dir = os.path.dirname(local_filename)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)
        print("downloading {} ...".format(local_filename), flush=True, end="")
        try:
            urllib.request.urlretrieve(url, local_filename)
        except urllib.error.HTTPError as e:
            if mandatory:
                print("failed")
                raise e
            print("skipped, not mandatory")
        else:
            print("downloaded")

    def _cleanup(self):
        print("cleaning up directory")
        for item in os.listdir():
            if os.path.isfile(item) or os.path.islink(item):
                os.remove(item)
            elif os.path.isdir(item):
                shutil.rmtree(item)

    def preprocess(self):
        pass

    def download(self):
        pass

    def postprocess(self):
        pass


class GkiDownloader(Downloader):
    def preprocess(self):
        self._cleanup()

    def download(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, "ci_target_mapping.json")
        with open(json_path, "r", encoding="utf-8") as f:
            download_configs = json.load(f).get("download_configs")

        for filename, config in download_configs.items():
            self._download_artifact(
                config["remote_filename_fmt"].format(build_number=self.build_id),
                filename,
                mandatory=config["mandatory"],
            )

    def postprocess(self):
        if not os.path.exists("signed/boot-img.tar.gz"):
            os.symlink("../boot-img.tar.gz", "signed/boot-img.tar.gz")
            with open("signed/NOT_SIGNED", "w") as f:
                f.write("This build is not signed, use unsigned boot images.\n")


TARGET_DOWNLOADERS = {
    "kernel_aarch64": GkiDownloader,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-d", "--directory",
        type=str,
        help=(
            "the directory to download the prebuilts, existing files in the directory will be"
            " removed before downloading; default to prebuilts/gki/BUILD_TARGET"
        )
    )
    parser.add_argument(
        "-t", "--build_target",
        type=str,
        help='the build target to download, e.g. "kernel_aarch64"',
        required=True,
    )
    parser.add_argument(
        "-b", "--build_id",
        type=str,
        help="the build id to download the build for, e.g. 12345678",
        required=True,
    )
    parser.add_argument(
        "-f", "--force",
        help="do not prompt when the directory exists",
        action=argparse.BooleanOptionalAction,
    )
    args = parser.parse_args()

    if args.build_target not in TARGET_DOWNLOADERS:
        print("{} is not supported".format(args.build_target))
        sys.exit(1)

    downloader = TARGET_DOWNLOADERS[args.build_target](args.build_id, args.build_target)

    directory = args.directory

    if directory is None:
        directory = os.path.join("prebuilts/gki", args.build_target)

    if os.path.isfile(directory):
        print("{} is not a directory".format(directory))
        sys.exit(1)

    if os.path.isdir(directory):
        if not args.force:
            user_input = input(
                f"The existing files in {directory} will be removed, continue? [y/N] "
            )
            if user_input.lower() not in ["y", "yes"]:
                print("Abort")
                sys.exit(1)
    else:
        os.makedirs(directory)

    os.chdir(directory)

    downloader.preprocess()
    downloader.download()
    downloader.postprocess()
