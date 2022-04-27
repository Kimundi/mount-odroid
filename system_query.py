import subprocess
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Extra


class Mount(BaseModel, extra=Extra.allow):
    _parent: Optional["Mount"]
    target: str
    source: str
    fstype: str
    options: str


class MountList:
    def __init__(self, dev: str):
        self.output = self.load(dev)
        self.mounts: List[Mount] = []

        # print(json.dumps(self.output, indent=4))

        for device in self.output["filesystems"]:
            self.parse_mount(device, None)

    def load(self, dev: str):
        ret = subprocess.run(
            [
                "findmnt",
                "--bytes",
                "--all",
                "--json",
                "--source",
                dev,
                "--tree",
                "--output-all",
            ],
            check=True,
            capture_output=True,
        )

        out = ret.stdout
        return json.loads(out)

    def parse_mount(self, raw: Dict[str, Any], parent: Optional[Mount]):
        children = raw.pop("children", [])

        obj = Mount.parse_obj(raw)
        obj._parent = parent
        self.mounts.append(obj)

        for child in children:
            self.parse_mount(child, obj)


class Device(BaseModel, extra=Extra.allow):
    _parent: Optional["Device"]
    _mounts: List["Mount"]

    kname: str
    type: str
    path: str
    model: Optional[str]
    fstype: Optional[str]
    partuuid: Optional[str]
    ptuuid: Optional[str]
    uuid: Optional[str]
    size: int
    fsused: Optional[int]
    fssize: Optional[int]
    fsavail: Optional[int]
    ro: Optional[bool]
    mountpoint: Optional[str]
    mountpoints: List[Optional[str]]
    fsroots: List[Optional[str]]
    serial: Optional[str]


class DeviceList:
    def __init__(self):
        self.output = self.load()
        self.devices: List[Device] = []

        # print(json.dumps(self.output, indent=4))

        for device in self.output["blockdevices"]:
            self.parse_disk(device, None)

    def load(self):
        ret = subprocess.run(
            [
                "lsblk",
                "-abJO",
                "--tree",
            ],
            check=True,
            capture_output=True,
        )

        out = ret.stdout
        return json.loads(out)

    def parse_disk(self, raw: Dict[str, Any], parent: Optional[Device]):
        children = raw.pop("children", [])

        obj = Device.parse_obj(raw)
        obj._parent = parent

        if (path := obj.path) is not None:
            mounts = MountList(path).mounts
            obj._mounts = mounts

        self.devices.append(obj)

        for child in children:
            self.parse_disk(child, obj)
