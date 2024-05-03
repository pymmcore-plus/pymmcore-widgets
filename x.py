import useq
from rich import print

seq = useq.MDASequence(
    channels=["DAPI", "FITC"],
    stage_positions=[
        (1, 2, 3),
        {
            "x": 4,
            "y": 5,
            "z": 6,
            "sequence": useq.MDASequence(grid_plan={"rows": 2, "columns": 1}),
        },
    ],
    time_plan={"interval": 0, "loops": 3},
    z_plan={"range": 2, "step": 0.7},
)

print("main", seq.sizes)
print("p0", seq.stage_positions[0].sequence)
print("p1", seq.stage_positions[1].sequence.sizes)
