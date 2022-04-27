#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import pprint
import copy
from typing import Optional

from table_formatting import TableFormatter


class Mounter:
    def __init__(self):
        self.mounted = []
        self.mountable = []
        self.mountstate = None
        self.devices = None
        self.collect()

    def collect(self):
        ret = subprocess.run(
            [
                "lsblk",
                "-Jao",
                "KNAME,TYPE,SIZE,MODEL,FSTYPE,UUID,FSAVAIL,FSUSE%,MOUNTPOINT,LABEL",
            ],
            check=True,
            capture_output=True,
        )
        # ret = subprocess.run(["lsblk", "-JaO"], check=True, capture_output=True)

        out = ret.stdout
        data = json.loads(out)

        self.devices = data["blockdevices"]

        self.mounted = []
        self.mountable = []

        for e in self.devices:
            if e["mountpoint"] is not None:
                self.mounted.append(e)
                continue
            if e["fstype"] is not None:
                self.mountable.append(e)
                continue
            # print(e)

        self.mountstate = subprocess.run(
            ["mount"], check=True, capture_output=True, encoding="utf-8"
        ).stdout.splitlines()

    def get_mountstate(self, dev) -> Optional[str]:
        dev = str(dev)
        for line in self.mountstate:
            if line.startswith(f"{dev} "):
                # print(line, dev)
                p = line.rfind("(")
                return line[p + 1 : -1]
        return None


def main0():
    mounter = Mounter()

    print("[Mounted]")
    output(mounted)

    print("[Mountable]")
    output(mountable)

    def find_dev():
        i = 0
        while any(e["mountpoint"] == f"/mnt/disk{i}" for e in mounted):
            # print(f"/mnt/disk{i} is already mounted")
            i += 1
        p = Path(f"/mnt/disk{i}")
        p.mkdir(parents=True, exist_ok=True)
        return p

    print("[Mount Devices]")
    for dev in mountable:
        dev_path = f"/dev/{dev['kname']}"
        if dev.get("fstype") == "swap":
            print(f"Skip swap partition {dev_path}")
            continue
        if (
            dev.get("fstype") == "vfat"
            and dev.get("size") is not None
            and dev["size"].endswith("M")
        ):
            print(f"Skip small FAT partition {dev_path}")
            continue

        mount_path = find_dev()
        inp = input(f"Mount {dev_path} to {mount_path}? [y|n] ")
        if inp.startswith("y"):
            # mount -o ro /dev/sda2 /mnt/disk0
            subprocess.run(
                ["mount", "-o", "ro,noatime", dev_path, mount_path], check=True
            )
        collect()

    print()
    print("All disks are available under /mnt and the mnt samba share")
    print("Done")


main0()
