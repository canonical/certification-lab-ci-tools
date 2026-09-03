from configparser import ConfigParser
from pathlib import Path
from typing import Optional, Sequence


class CheckBoxConfiguration(ConfigParser):
    def __init__(self):
        super().__init__(delimiters=("=",))

    def optionxform(self, optionstr: str) -> str:
        return str(optionstr)

    @property
    def description(self) -> Optional[str]:
        return self.get("launcher", "session_desc", fallback=None)

    @description.setter
    def description(self, value: str):
        if value is None:
            return
        try:
            launcher_section = self["launcher"]
        except KeyError:
            # there is no launcher section, so it needs to be created
            self["launcher"] = {"session_desc": value}
        else:
            launcher_section["session_desc"] = value

    def write_to_file(self, path: Path):
        with open(path, "w") as file:
            self.write(file)

    def stack(
        self, paths: Sequence[Path], output: Path, description: Optional[str] = None
    ):
        # stack *all* configuration files, in the specified order
        # (read is inconvenient, it doesn't mind non-existent files)
        for path in paths:
            with open(path) as file:
                self.read_file(file)
        # add description
        self.description = description
        # write stacked configuration file
        self.write_to_file(output)
