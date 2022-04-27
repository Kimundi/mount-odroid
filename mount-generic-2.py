#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import pprint
import copy
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ValidationError, Extra

from table_formatting import TableFormatter
from system_query import Device, DeviceList


def passthrough(obj: Dict[str, Any], key: str) -> Any:
    return obj.get(key)


def sizefmt(obj: Dict[str, Any], key: str) -> Any:
    units = {
        1024**4: "TiB",
        1024**3: "GiB",
        1024**2: "MiB",
        1024**1: "KiB",
        1024**0: "B  ",
    }

    e = obj.get(key)
    if e is None:
        return None

    for unit_size, unit_name in units.items():
        if e >= unit_size:
            return f"{e / unit_size:0.1f} {unit_name}"

    return "<err>"


def parent(obj: Dict[str, Any], key: str) -> Any:
    obj = obj["_parent"]
    return passthrough(obj, key)


def filter_disk(dev: Device):
    keys = {
        "path": passthrough,
        "size": sizefmt,
        "model": passthrough,
        "serial": passthrough,
    }

    return {k: keys[k](dev.dict(), k) for k in keys}


def filter_part(dev: Device):
    def mountoptions(obj: Dict[str, Any], key: str):
        try:
            assert len(obj["_mounts"]) <= 1
            return obj["_mounts"][0]["options"]
        except IndexError:
            return None

    keys = {
        "path": passthrough,
        "label": passthrough,
        "fstype": passthrough,
        "mountpoint": passthrough,
        "mountoptions": mountoptions,
        "size": sizefmt,
        "fssize": sizefmt,
        "fsavail": sizefmt,
        "uuid": passthrough,
        "model": parent,
        "serial": parent,
    }

    return {k: keys[k](dev.dict(), k) for k in keys}


def main():
    devices = DeviceList().devices

    disks = []
    parts = []

    for device in devices:
        # print(disk.json(exclude_none=True, indent=4))
        assert device.type in ("disk", "part")

        if device.type == "disk":
            disks.append(filter_disk(device))
        elif device.type == "part":
            parts.append(filter_part(device))

    print("[Disks]")
    # print(json.dumps(disks, indent=4))
    disk_table = TableFormatter()
    for disk in disks:
        disk_table.append(disk, False)
    disk_table.print()

    print("[Partitions]")
    # print(json.dumps(parts, indent=4))
    part_table = TableFormatter()
    for part in parts:
        part_table.append(part, False)
    part_table.print()


if __name__ == "__main__":
    main()
