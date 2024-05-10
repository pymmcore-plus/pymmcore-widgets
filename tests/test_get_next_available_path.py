from pathlib import Path

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
tiff_files = [
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


@pytest.mark.parametrize("starting_files, tiff_file, expected", tiff_files)
def test_ome_writers_multi_pos(
    tmp_path: Path,
    starting_files: list,
    tiff_file: str,
    expected: str,
):
    # create the starting files
    for file in starting_files:
        (tmp_path / file).touch()

    # assert that the next available path is the expected one
    next_path = get_next_available_path(tmp_path / tiff_file)
    assert next_path.name == expected
