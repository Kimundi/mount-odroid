import json
from typing import Any, Dict, Optional


class TableFormatter:
    def __init__(self):
        self.ctx: Dict[str, Dict[str, Any]] = {}

    def append(
        self,
        columns: Dict[str, str],
        header=True,
        align: Optional[Dict[str, str]] = None,
    ):
        columns = {k: v for k, v in columns.items()}
        columns["_header"] = header

        align = align or {}

        count = None
        for val in self.ctx.values():
            if count is None:
                count = len(val)
            else:
                assert len(val) == count
        if count is None:
            count = 0

        for key in columns.keys():
            self.ctx.setdefault(
                key,
                {
                    "columns": [""] * count,
                    "width": len(key),
                },
            )

        for key, val in self.ctx.items():
            val2 = columns.get(key)
            if val2 is None:
                val2 = ""
            if isinstance(val2, bool):
                val2 = str(val2)
            assert isinstance(val2, str)
            val["columns"].append(val2)
            val["width"] = max(val["width"], len(val2))
            # print(align, key)
            val["align"] = align.get(key, "")

    def print(self):
        # print(json.dumps(self.ctx, indent=4))

        for key in list(self.ctx.keys()):
            if all(e == "" for e in self.ctx[key]["columns"]):
                del self.ctx[key]

        sep = "│"
        line = ""
        for key, val in self.ctx.items():
            if key == "_header":
                continue
            key: str = key.upper()
            line += f"{key:{val['width']}}{sep}"
        print(line)

        i = 0
        while True:
            breakout = False
            line = ""
            for key, val in self.ctx.items():
                if key == "_header":
                    continue
                columns = val["columns"]
                if i >= len(columns):
                    breakout = True
                    break
                column = columns[i]

                if val["align"] == ">":
                    line += f"{column:>{val['width']}}{sep}"
                else:
                    line += f"{column:{val['width']}}{sep}"
            if breakout:
                break
            if i == 0 or self.ctx["_header"]["columns"][i] == "True":
                # print()
                print("─" * len(line))
                pass
            print(line)
            if self.ctx["_header"]["columns"][i] == "True":
                # print("─" * len(line))
                pass
            i += 1
        print()
