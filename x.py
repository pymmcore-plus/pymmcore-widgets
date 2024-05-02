import useq
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMEZarrWriter

core = CMMCorePlus()
core.loadSystemConfiguration()
seq = useq.MDASequence(
    channels=["DAPI", "FITC"],
    stage_positions=[(1, 2, 3)],
    time_plan={"interval": 0, "loops": 3},
    grid_plan={"rows": 2, "columns": 1},
    z_plan={"range": 2, "step": 0.7},
)
writer = OMEZarrWriter()
core.mda.run(seq, output=writer)

xa = writer.as_xarray()
da = xa["p0"]
print(da)
print(da.dims)
