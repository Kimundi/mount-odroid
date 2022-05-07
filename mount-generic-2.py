#!/usr/bin/env python3

from dataclasses import dataclass
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
    e = obj.get(key)
    return str(e) if e is not None else None


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
        "pttype": passthrough,
        "rota": passthrough,
        "ro": passthrough,
        "rm": passthrough,
    }

    # print(dev.json(indent=4))

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


@dataclass
class CmdState:
    disks: List[dict]
    parts: List[dict]
    mounted: Dict[str, dict]
    unmounted: Dict[str, dict]


def cmd_state() -> CmdState:
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

    mounted = {}
    unmounted = {}
    for part in parts:
        if part.get("mountpoint"):
            mounted[f"M{len(mounted)}"] = part
        else:
            unmounted[f"U{len(unmounted)}"] = part

    return CmdState(
        disks=disks,
        parts=parts,
        mounted=mounted,
        unmounted=unmounted,
    )


def cmd_disks(state: CmdState):
    print("[Disks]")
    # print(json.dumps(disks, indent=4))
    disk_table = TableFormatter()
    for disk in state.disks:
        disk_table.append(
            disk,
            False,
            align={
                "size": ">",
                "serial": ">",
            },
        )
    disk_table.print()


def cmd_parts(state: CmdState):
    print("[Partitions]")
    # print(json.dumps(parts, indent=4))
    part_table = TableFormatter()
    for part in state.parts:
        part_table.append(
            part,
            False,
            align={
                "size": ">",
                "fssize": ">",
                "fsavail": ">",
                "serial": ">",
            },
        )
    part_table.print()


def cmd_mounting(state: CmdState):
    action = "initial"
    while action != "back":
        for part_kind_name, part_dict in [
            ("Mounted", state.mounted),
            ("Unmounted", state.unmounted),
        ]:
            print(f"[{part_kind_name} Partitions]")
            # print(json.dumps(parts, indent=4))
            part_table = TableFormatter()
            for key, part in part_dict.items():
                part2 = {}
                part2["#"] = key
                part2.update(part)
                del part2["uuid"]
                part_table.append(
                    part2,
                    False,
                    align={
                        "size": ">",
                        "fssize": ">",
                        "fsavail": ">",
                        "serial": ">",
                    },
                )
            part_table.print()

        # print("What do you want to do?")

        action = ask_options(
            [
                "mount",
                "unmount",
                "back",
            ]
        )

        if action == "mount":
            pass
        elif action == "unmount":
            pass


def main():
    cmd_mounting(cmd_state())
    while True:
        state = cmd_state()
        action = ask_options(
            [
                "mounting",
                "disks",
                "parts",
                "quit",
            ]
        )
        if action == "mounting":
            cmd_mounting(state)
        elif action == "disks":
            cmd_disks(state)
        elif action == "parts":
            cmd_parts(state)
        else:
            break


def ask_options(cases: list) -> str:
    while True:
        v = input("[" + ",".join(cases) + "]? ").lower()
        selected = set()
        for case in cases:
            if case.lower().startswith(v):
                selected.add(case)
        if len(selected) == 1:
            return next(iter(selected))
        else:
            print("Invalid input")


if __name__ == "__main__":
    main()
