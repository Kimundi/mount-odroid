#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import pprint
import copy


def main0():
    mounted = []
    mountable = []
    mountstate = None
    devices = None

    def collect():
        nonlocal mounted
        nonlocal mountable
        nonlocal mountstate
        nonlocal devices

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

        devices = data["blockdevices"]

        mounted = []
        mountable = []

        for e in devices:
            if e["mountpoint"] is not None:
                mounted.append(e)
                continue
            if e["fstype"] is not None:
                mountable.append(e)
                continue
            # print(e)

        mountstate = subprocess.run(
            ["mount"], check=True, capture_output=True, encoding="utf-8"
        ).stdout.splitlines()

    collect()

    def get_mountstate(dev):
        dev = str(dev)
        for line in mountstate:
            if line.startswith(f"{dev} "):
                # print(line, dev)
                p = line.rfind("(")
                return line[p + 1 : -1]
        return None

    def append_ctx(ctx, columns):
        count = None
        for val in ctx.values():
            if count is None:
                count = len(val)
            else:
                assert len(val) == count
        if count is None:
            count = 0

        for key, value in columns.items():
            ctx.setdefault(key, {"columns": [""] * count, "width": len(key)})

        for key, val in ctx.items():
            val2 = columns.get(key)
            if val2 is None:
                val2 = ""
            if isinstance(val2, bool):
                val2 = str(val2)
            assert isinstance(val2, str)
            val["columns"].append(val2)
            val["width"] = max(val["width"], len(val2))

    def print_ctx(ctx):
        for key in list(ctx.keys()):
            if all(e == "" for e in ctx[key]["columns"]):
                del ctx[key]

        sep = "│"
        line = ""
        for key, val in ctx.items():
            if key == "_header":
                continue
            key: str = key.upper()
            line += f"{key:{val['width']}}{sep}"
        print(line)

        i = 0
        while True:
            breakout = False
            line = ""
            for key, val in ctx.items():
                if key == "_header":
                    continue
                columns = val["columns"]
                if i >= len(columns):
                    breakout = True
                    break
                column = columns[i]

                if key == "size":
                    line += f"{column:>{val['width']}}{sep}"
                else:
                    line += f"{column:{val['width']}}{sep}"
            if breakout:
                break
            if ctx["_header"]["columns"][i] == "True":
                # print()
                print("─" * len(line))
                pass
            print(line)
            if ctx["_header"]["columns"][i] == "True":
                # print("─" * len(line))
                pass
            i += 1

    def fmt(v, header, ctx):
        indent = "  "
        if header:
            indent = ""

        assert isinstance(v, dict)

        v: dict = copy.deepcopy(v)
        kname = v.pop("kname")
        dev = Path(f"/dev/{kname}")
        assert dev.exists()

        # Setting to empty string so that the column does not get filtered
        ty = v.pop("type") or ""
        size = v.pop("size") or ""
        fstype = v.pop("fstype") or ""
        uuid = v.pop("uuid") or ""
        label = v.pop("label") or ""
        mountpoint = v.pop("mountpoint")
        mountopts = get_mountstate(dev)

        columns = {
            "_header": header,
            "type": f"{indent}{ty}",
            "device": f"{dev}",
            "filesystem": f"{fstype}",
            "label": f"{label}",
            "size": f"{size}",
            "mountpoint": mountpoint,
            "mountopts": mountopts,
            **v,
            "uuid": f"{uuid}",
        }

        # print(columns)

        append_ctx(ctx, columns)

    def find_parent(e):
        for pe in devices:
            pn = pe["kname"]
            n = e["kname"]
            if n.startswith(pn) and n != pn:
                return pe
        return None

    def output(list):
        ctx = {}
        last_device = None
        for e in list:
            is_child = find_parent(e) is not None
            if last_device is not find_parent(e):
                last_device = find_parent(e)
                if last_device is not None:
                    fmt(last_device, True, ctx)
            fmt(e, not is_child, ctx)
        print_ctx(ctx)
        print()

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
