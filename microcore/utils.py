import builtins
import dataclasses
import inspect
import json
import os
import sys
import re
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from colorama import Fore

from .configuration import Config
from .types import BadAIAnswer
from .message_types import UserMsg, SysMsg, AssistantMsg


def is_chat_model(model: str, config: Config = None) -> bool:
    """Detects if model is chat model or text completion model"""
    if config and config.CHAT_MODE is not None:
        return config.CHAT_MODE
    completion_keywords = ["instruct", "davinci", "babbage", "curie", "ada"]
    return not any(keyword in str(model).lower() for keyword in completion_keywords)


class ConvertableToMessage:
    @property
    def as_user(self) -> UserMsg:
        return UserMsg(str(self))

    @property
    def as_system(self) -> SysMsg:
        return SysMsg(str(self))

    @property
    def as_assistant(self) -> AssistantMsg:
        return AssistantMsg(str(self))

    @property
    def as_model(self) -> AssistantMsg:
        return self.as_assistant


class ExtendedString(str):
    """
    Provides a way of extending string with attributes and methods
    """

    def __new__(cls, string: str, attrs: dict = None):
        """
        Allows string to have attributes.
        """
        obj = str.__new__(cls, string)
        if attrs:
            for k, v in attrs.items():
                setattr(obj, k, v)
        return obj

    def __getattr__(self, item):
        """
        Provides chaining of global functions
        """
        global_func = inspect.currentframe().f_back.f_globals.get(item) or vars(
            builtins
        ).get(item, None)
        if callable(global_func):

            def method_handler(*args, **kwargs):
                res = global_func(self, *args, **kwargs)
                if isinstance(res, str) and not isinstance(res, ExtendedString):
                    res = ExtendedString(res)
                return res

            return method_handler

        # If there's not a global function with that name, raise an AttributeError as usual
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{item}'"
        )


class DataclassEncoder(json.JSONEncoder):
    """@private"""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


json.JSONEncoder.default = DataclassEncoder().default


def parse(
    text: str, field_format: str = r"\[\[(.*?)\]\]", required_fields: list = None
) -> dict:
    """
    Parse a document divided into sections and convert it into a dictionary.
    """
    pattern = rf"{field_format}\n(.*?)(?=\n{field_format}|$)"
    matches = re.findall(pattern, text, re.DOTALL)
    result = {key.strip().lower(): value for key, value, _ in matches}
    if required_fields:
        for field in required_fields:
            if field not in result:
                raise BadAIAnswer(f"Field '{field}' is required but not found")
    return result


def file_link(file_path: str | Path):
    """Returns file name in format displayed in PyCharm console as a link."""
    return "file:///" + str(Path(file_path).absolute()).replace("\\", "/")


def list_files(
    target_dir: str | Path = "",
    exclude: list[str | Path] = None,
    relative_to: str | Path = None,
    absolute: bool = False,
    posix: bool = False,
) -> list[Path]:
    """
    Lists files in a specified directory, excluding those that match given patterns.

    This function traverses the specified directory recursively and returns a list of all files
    that do not match the specified exclusion patterns. It can return absolute paths,
    paths relative to the target directory, or paths relative to a specified directory.

    Args:
        target_dir (str | Path): The directory to search in.
        exclude (list[str | Path]): Patterns of files to exclude.
        relative_to (str | Path, optional): Base directory for relative paths.
            If None, paths are relative to `target_dir`. Defaults to None.
        absolute (bool, optional): If True, returns absolute paths. Defaults to False.
        posix (bool, optional): If True, returns posix paths. Defaults to False.

    Returns:
        list[Path]: A list of Path objects representing the files found.

    Example:
        exclude_patterns = ['*.pyc', '__pycache__/*']
        target_directory = '/path/to/target'
        files = list_files(target_directory, exclude_patterns)
    """
    exclude = exclude or []
    target = Path(target_dir or os.getcwd()).resolve()
    relative_to = Path(relative_to).resolve() if relative_to else None
    if absolute and relative_to is not None:
        raise ValueError(
            "list_files(): Cannot specify both 'absolute' and 'relative_to'. Choose one."
        )
    return [
        p.as_posix() if posix else p
        for p in (
            path.resolve() if absolute else path.relative_to(relative_to or target)
            for path in target.rglob("*")
            if path.is_file()
            and not any(
                fnmatch(str(path.relative_to(target)), str(pattern))
                for pattern in exclude
            )
        )
    ]


def is_kaggle() -> bool:
    return "KAGGLE_KERNEL_RUN_TYPE" in os.environ


def is_notebook() -> bool:
    return "ipykernel" in sys.modules


def is_google_colab() -> bool:
    return "google.colab" in sys.modules


def get_vram_usage(as_string=True, color=Fore.GREEN):
    @dataclass
    class _MemUsage:
        name: str
        used: int
        free: int
        total: int

    cmd = (
        "nvidia-smi"
        " --query-gpu=name,memory.used,memory.free,memory.total"
        " --format=csv,noheader,nounits"
    )
    try:
        out = subprocess.check_output(cmd, shell=True, text=True).strip()

        mu = [
            _MemUsage(*[i.strip() for i in line.split(",")])
            for line in out.splitlines()
        ]
        if not as_string:
            return mu
        c, r = (color, Fore.RESET) if color else ("", "")
        return "\n".join(
            [
                f"GPU: {c}{i.name}{r}, "
                f"VRAM: {c}{i.used}{r}/{c}{i.total}{r} MiB used, "
                f"{c}{i.free}{r} MiB free"
                for i in mu
            ]
        )
    except subprocess.CalledProcessError:
        msg = "No GPU found or nvidia-smi is not installed"
        return f"{Fore.RED}{msg}{Fore.RESET}" if as_string else None


def show_vram_usage():
    print(get_vram_usage(as_string=True))


def return_default(default, *args):
    if isinstance(default, type) and issubclass(default, BaseException):
        raise default()
    if isinstance(default, BaseException):
        raise default
    if inspect.isbuiltin(default):
        return default(*args)
    if inspect.isfunction(default):
        arg_count = default.__code__.co_argcount
        if inspect.ismethod(default):
            arg_count -= 1
        return default(*args) if arg_count >= len(args) else default()

    return default


def extract_number(
    text: str,
    default=None,
    position="last",
    dtype: type | str = float,
    rounding: bool = False,
) -> int | float | Any:
    assert position in ["last", "first"], f"Invalid position: {position}"
    idx = {"last": -1, "first": 0}[position]

    dtype = {"int": int, "float": float}.get(dtype, dtype)
    assert dtype in [int, float], f"Invalid dtype: {dtype}"
    if rounding:
        dtype = float
    regex = {int: r"[-+]?\d+", float: r"[-+]?\d*\.?\d+"}[dtype]

    numbers = re.findall(regex, str(text))
    if numbers:
        try:
            value = dtype(numbers[idx].strip())
            return round(value) if rounding else value
        except ValueError:
            ...
    return return_default(default, text)
