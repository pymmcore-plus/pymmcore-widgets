from pathlib import Path
from typing import Callable

import pytest

from pymmcore_widgets._util import get_next_available_path

starting_tiff_files_0 = [
    "out_006.ome.tiff",
    "out_002_p0.ome.tiff",
    "out_002_p1.ome.tiff",
]
starting_tiff_files_1 = [*starting_tiff_files_0, "out_007_p2.ome.tiff"]
starting_tiff_files_2 = [*starting_tiff_files_1, "out_008_p0_test.ome.tiff"]
starting_zarr_files = ["out.ome.zarr", "out_002.ome.zarr"]
starting_tiff_sequence = ["out", "out_002"]

# starting files in temp dir, requested file, expected next file
files = [
    (starting_tiff_files_0, "out.ome.tiff", "out_007.ome.tiff"),
    (starting_tiff_files_0, "out_001.ome.tiff", "out_007.ome.tiff"),
    (starting_tiff_files_2, "out_005.ome.tiff", "out_008.ome.tiff"),
    (starting_tiff_files_2, "out_006.ome.tiff", "out_008.ome.tiff"),
    (starting_tiff_files_2, "out_001_p0.ome.tiff", "out_008.ome.tiff"),
    (starting_tiff_files_2, "out_009_pos0.ome.tiff", "out_009_pos0.ome.tiff"),
    (starting_zarr_files, "out.ome.zarr", "out_003.ome.zarr"),
    (starting_zarr_files, "out_p0.ome.zarr", "out_p0.ome.zarr"),
    (starting_zarr_files, "output.ome.zarr", "output.ome.zarr"),
    (starting_tiff_sequence, "out_001", "out_003"),
    (starting_tiff_sequence, "test", "test"),
]


@pytest.mark.parametrize("starting_files, file, expected", files)
def test_ome_writers_multi_pos(
    tmp_path: Path,
    starting_files: list,
    file: str,
    expected: str,
):
    # create the starting files
    for f in starting_files:
        (tmp_path / f).touch()

    # assert that the next available path is the expected one
    next_path = get_next_available_path(tmp_path / file)
    assert next_path.name == expected


@pytest.mark.parametrize("extension", [".ome.tiff", ".ome.tif", ".ome.zarr", ""])
def test_get_next_available_paths(extension: str, tmp_path: Path) -> None:
    # non existing paths returns the same path
    path = tmp_path / f"test{extension}"
    assert get_next_available_path(path) == path

    make: Callable = Path.mkdir if extension in {".ome.zarr", ""} else Path.touch

    # existing files add a counter to the path
    make(path)
    assert get_next_available_path(path) == tmp_path / f"test_001{extension}"

    # if a path with a counter exists, the next (maximum) counter is used
    make(tmp_path / f"test_004{extension}")
    assert get_next_available_path(path) == tmp_path / f"test_005{extension}"


def test_get_next_available_paths_special_cases(tmp_path: Path) -> None:
    base = tmp_path / "test.txt"
    assert get_next_available_path(base).name == base.name

    # only 3+ digit numbers are considered as counters
    (tmp_path / "test_04.txt").touch()
    assert get_next_available_path(base).name == base.name

    # if an existing thing with a higher number is there, the next number is used
    # (even if the requested path does not exist, but has a lower number)
    (tmp_path / "test_004.txt").touch()
    assert get_next_available_path(tmp_path / "test_003.txt").name == "test_005.txt"

    # if we explicitly ask for a higher number, we should get it
    assert get_next_available_path(tmp_path / "test_010.txt").name == "test_010.txt"

    # only 3+ digit numbers are considered as counters
    assert get_next_available_path(tmp_path / "test_02.txt").name == "test_02.txt"
    # unless the requested path exists
    assert get_next_available_path(tmp_path / "test_04.txt").name == "test_04_001.txt"

    # we go to the next number of digits if need be
    (tmp_path / "test_999.txt").touch()
    assert get_next_available_path(base).name == "test_1000.txt"

    # more than 3 digits are used as is
    high = tmp_path / "test_12345.txt"
    high.touch()
    assert get_next_available_path(high).name == "test_12346.txt"
