#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import pprint
import copy
from typing import Optional

from table_formatting import TableFormatter


class DeviceState:
    def __init__(self):
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
        data = json.loads(out)
        self.output = data

        print(json.dumps(self.output, indent=4))


def main():
    state = DeviceState()


if __name__ == "__main__":
    main()
