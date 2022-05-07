#!/usr/bin/env python3

from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
import copy
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ValidationError, Extra
from rich import print
from rich.markup import escape
import shlex
import subprocess

from table_formatting import TableFormatter
from system_query import Device, DeviceList

old_input = input


def input(prompt=None, default=None) -> str:
    if prompt:
        print(prompt, end="")
    ret = old_input()
    if ret.strip() == "" and default:
        return default
    return ret


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


def filter_disk(dev: Device) -> Dict[str, Any]:
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
    disks_dict: Dict[str, dict]

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

    disks_dict = {}
    for disk in disks:
        disks_dict[f"D{len(disks_dict)}"] = disk

    return CmdState(
        disks=disks,
        parts=parts,
        mounted=mounted,
        unmounted=unmounted,
        disks_dict=disks_dict,
    )


def print_heading(n: str):
    print(f"[bright_green]\[{n}][/]")


def cmd_show_disks(state: CmdState):
    print_heading("Disks")
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


def cmd_show_parts(state: CmdState):
    print_heading("Partitions")
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


def cmd_show_mounting(state: CmdState, flip=False):
    if flip:
        cases = [
            ("Unmounted", state.unmounted),
            ("Mounted", state.mounted),
        ]
    else:
        cases = [
            ("Mounted", state.mounted),
            ("Unmounted", state.unmounted),
        ]

    for part_kind_name, part_dict in cases:
        print_heading(f"{part_kind_name} Partitions")
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


def cmd_mount(state: CmdState):
    cmd_show_mounting(state)
    options = list(state.unmounted.keys()) + ["abort"]
    resp = input_options(options, "Which partition do you want to mount? ")
    if resp == "abort":
        return

    part = state.unmounted[resp]
    label = part.get("label")
    if label is None:
        label = "unlabeled"

    mountpoint_default = f"/disks/{label}"
    mountpoint = Path(
        input(f"Mountpoint? \[{mountpoint_default}]: ", default=mountpoint_default)
    )

    if not mountpoint.exists():
        resp = input_options(
            ["yes", "sudo_yes", "no"], f"Create directory for mountpoint {mountpoint}? "
        )
        if resp == "no":
            return
        elif resp in ("yes", "sudo_yes"):
            if resp == "sudo_yes":
                cmdline = ["sudo"]
            else:
                cmdline = []
            cmdline.extend(["mkdir", "-p", str(mountpoint)])
            resp = confirm_cmdline(cmdline)
            if resp == "no":
                return

    read_only = input_options(["yes", "no"], "Mount read-only? ")
    read_only = read_only != "no"

    mount_options = [
        "noatime",
    ]
    if read_only:
        mount_options.append("ro")

    confirm_cmdline(
        [
            "sudo",
            "mount",
            "-o",
            ",".join(mount_options),
            part["path"],
            mountpoint_default,
        ]
    )


def confirm_cmdline(cmdline: List[str]):
    cmdline_j = shlex.join(cmdline)
    resp = input_options(["yes", "no"], f"Execute `{cmdline_j}`? ")
    subprocess.run(cmdline, check=True)
    return resp


def cmd_unmount(state: CmdState):
    cmd_show_mounting(state, flip=True)
    options = list(state.mounted.keys()) + ["abort"]
    resp = input_options(options, "Which partition do you want to unmount? ")
    if resp == "abort":
        return

    part = state.mounted[resp]
    confirm_cmdline(
        [
            "sudo",
            "umount",
            part["mountpoint"],
        ]
    )


def cmd_eject(state: CmdState):
    print_heading(f"Disks")
    # print(json.dumps(parts, indent=4))
    part_table = TableFormatter()
    for key, disk in state.disks_dict.items():
        disk2 = {}
        disk2["#"] = key
        disk2.update(disk)
        part_table.append(
            disk2,
            False,
            align={
                "size": ">",
                "serial": ">",
            },
        )
    part_table.print()


def main():
    cmd_show_mounting(cmd_state())
    while True:
        state = cmd_state()
        try:
            action = input_options(
                [
                    "disks",
                    "parts",
                    "mount",
                    "unmount",
                    "eject",
                    "smart",
                    "quit",
                ]
            )
        except KeyboardInterrupt:
            action = "quit"

        if action == "mount":
            cmd_mount(state)
        elif action == "unmount":
            cmd_unmount(state)
        elif action == "disks":
            cmd_show_disks(state)
        elif action == "parts":
            cmd_show_parts(state)
        elif action == "eject":
            cmd_eject(state)
        elif action == "quit":
            break
        else:
            print(f"NOT IMPLEMENTED YET: {action}")


def input_options(cases: list, msg=None) -> str:
    while True:
        if not msg:
            msg = ""

        msg = (
            msg + f"\[" + ",".join(f"[bright_blue]{case}[/]" for case in cases) + "]: "
        )

        v = input(msg).lower()
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
