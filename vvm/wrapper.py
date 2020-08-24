import subprocess
from pathlib import Path
from typing import Any, List, Tuple, Union

from semantic_version import Version

from vvm import install
from vvm.exceptions import UnknownOption, UnknownValue, VyperError


def _get_vyper_version(vyper_binary: Union[Path, str]) -> Version:
    # private wrapper function to get `vyper` version
    stdout_data = subprocess.check_output([vyper_binary, "--version"], encoding="utf8")
    version_str = stdout_data.split("+")[0]
    return install._convert_and_validate_version(version_str)


def _to_string(key: str, value: Any) -> str:
    # convert data into a string prior to calling `vyper`
    if isinstance(value, (int, str)):
        return str(value)
    elif isinstance(value, Path):
        return value.as_posix()
    elif isinstance(value, (list, tuple)):
        return ",".join(_to_string(key, i) for i in value)
    else:
        raise TypeError(f"Invalid type for {key}: {type(value)}")


def vyper_wrapper(
    vyper_binary: Union[Path, str] = None,
    stdin: str = None,
    source_files: List = None,
    success_return_code: int = 0,
    **kwargs: Any,
) -> Tuple[str, str, List, subprocess.Popen]:
    """
    Wrapper function for calling to `vyper`.

    Arguments
    ---------
    vyper_binary : Path | str, optional
        Location of the `vyper` binary. If not given, the current default binary is used.
    stdin : str, optional
        Input to pass to `vyper` via stdin
    source_files : list, optional
        Paths of source files to compile
    success_return_code : int, optional
        Expected exit code. Raises `VyperError` if the process returns a different value.

    Keyword Arguments
    -----------------
    **kwargs : Any
        Flags to be passed to `vyper`. Keywords are converted to flags by prepending `--` and
        replacing `_` with `-`, for example the keyword `evm_version` becomes `--evm-version`.
        Values may be given in the following formats:

            * `False`, `None`: ignored
            * `True`: flag is used without any arguments
            * str: given as an argument without modification
            * int: given as an argument, converted to a string
            * Path: converted to a string via `Path.as_posix()`
            * List, Tuple: elements are converted to strings and joined with `,`

    Returns
    -------
    str
        Process `stdout` output
    str
        Process `stderr` output
    List
        Full command executed by the function
    Popen
        Subprocess object used to call `vyper`
    """
    if vyper_binary:
        vyper_binary = Path(vyper_binary)
    else:
        vyper_binary = install.get_executable()

    version = _get_vyper_version(vyper_binary)
    command: List = [vyper_binary]

    if source_files is not None:
        command.extend([_to_string("source_files", i) for i in source_files])

    for key, value in kwargs.items():
        if value is None or value is False:
            continue

        if len(key) == 1:
            key = f"-{key}"
        else:
            key = f"--{key.replace('_', '-')}"
        if value is True:
            command.append(key)
        else:
            command.extend([key, _to_string(key, value)])

    if stdin is not None:
        stdin = str(stdin)

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf8",
    )

    stdoutdata, stderrdata = proc.communicate(stdin)

    if proc.returncode != success_return_code:
        if stderrdata.startswith("unrecognised option"):
            # unrecognised option '<FLAG>'
            flag = stderrdata.split("'")[1]
            raise UnknownOption(f"Vyper {version} does not support the '{flag}' option'")
        if stderrdata.startswith("Invalid option"):
            # Invalid option to <FLAG>: <OPTION>
            flag, option = stderrdata.split(": ")
            flag = flag.split(" ")[-1]
            raise UnknownValue(
                f"Vyper {version} does not accept '{option}' as an option for the '{flag}' flag"
            )

        raise VyperError(
            command=command,
            return_code=proc.returncode,
            stdin_data=stdin,
            stdout_data=stdoutdata,
            stderr_data=stderrdata,
        )

    return stdoutdata, stderrdata, command, proc