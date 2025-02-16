#!/usr/bin/env python

import re
from pathlib import Path
from typing import Any, List, TextIO, Tuple

import h5py  # type: ignore
import numpy
import typer
from numpy.typing import NDArray
from typing_extensions import Annotated

from om.lib.exceptions import OmInvalidSourceError
from om.lib.logging import log

app = typer.Typer()


def main(
    input: Annotated[Path, typer.Argument(help="input")],
    output: Annotated[Path, typer.Argument(help="input")],
    s: Annotated[
        int,
        typer.Option(
            "--start-time",
            "-s",
            help="skip first images in the file",
        ),
    ] = 100,
) -> None:
    """
    Make dark calibration files from raw Jungfrau data.

    INPUT: text file containing list of dark files for one panel \n
    OUTPUT: output .h5 file
    """
    if not input.exists():
        raise RuntimeError(f"The following file cannot be found: {input}")

    const_dark: Tuple[int, int, int] = (0, 0, 0)
    fn: str
    try:
        fhandle: TextIO
        with open(input, "r") as fhandle:
            filelist: List[str] = [fn.strip() for fn in fhandle]
    except (IOError, OSError) as exc:
        raise OmInvalidSourceError(f"Error reading the {input} source file.") from exc

    n: int = 1024 * 512
    sd: NDArray[numpy.float_] = numpy.zeros((3, n), dtype=numpy.float64)
    nd: NDArray[numpy.float_] = numpy.zeros((3, n))
    for fn in filelist:
        i: int = int(re.findall("_f(\\d+)_", fn)[0])
        h5_data_path: str = "/data_" + f"f{i:012d}"
        f: Any
        with h5py.File(fn, "r") as f:
            n_frames: int = f[h5_data_path].shape[0]
            log.info("%s frames in %s" % (n_frames, fn))
            frame: NDArray[numpy.int_]
            for frame in f[h5_data_path][s:]:
                d: NDArray[numpy.int_] = frame.flatten()
                where_gain: List[Tuple[NDArray[numpy.int_], ...]] = [
                    numpy.where((d & 2**14 == 0) & (d > 0)),
                    numpy.where((d & (2**14) > 0) & (d & 2**15 == 0)),
                    numpy.where(d & 2**15 > 0),
                ]
                for i in range(3):
                    sd[i][where_gain[i]] += d[where_gain[i]]
                    nd[i][where_gain[i]] += 1

    with numpy.errstate(divide="ignore", invalid="ignore"):
        dark: NDArray[numpy.float_] = (sd / nd).astype(numpy.float32)

    if numpy.any(nd == 0):
        log.warning("Some pixels don't have data in all gains")
        for i in range(3):
            where: Tuple[NDArray[numpy.int_], ...] = numpy.where(nd[i] == 0)
            dark[i][where] = const_dark[i]
            log.warning(
                f"{len(where[0])} pixels in gain {i} are set to {const_dark[i]}",
            )

    with h5py.File(output, "w") as f:
        f.create_dataset("/gain0", data=dark[0].reshape(512, 1024))
        f.create_dataset("/gain1", data=dark[1].reshape(512, 1024))
        f.create_dataset("/gain2", data=dark[2].reshape(512, 1024))


if __name__ == "__main__":
    typer.run(main)
