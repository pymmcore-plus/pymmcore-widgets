from dataclasses import dataclass


@dataclass(frozen=True)
class WellPlate:
    """General well plates class."""

    id: str
    circular: bool
    rows: int
    cols: int
    well_spacing_x: float
    well_spacing_y: float
    well_size_x: float
    well_size_y: float

    @property
    def well_count(self) -> int:
        """Return the number of wells in the plate."""
        return self.rows * self.cols


PLATES = [
    WellPlate(
        circular=True,
        cols=6,
        id="VWR 24  Plastic",
        rows=4,
        well_size_x=15.7,
        well_size_y=15.7,
        well_spacing_x=19.2,
        well_spacing_y=19.2,
    ),
    WellPlate(
        circular=False,
        cols=1,
        id="_from calibration",
        rows=1,
        well_size_x=10.0,
        well_size_y=10.0,
        well_spacing_x=0,
        well_spacing_y=0,
    ),
    WellPlate(
        circular=False,
        cols=1,
        id="coverslip 22mm",
        rows=1,
        well_size_x=22.0,
        well_size_y=22.0,
        well_spacing_x=0.0,
        well_spacing_y=0.0,
    ),
    WellPlate(
        circular=True,
        cols=4,
        id="standard 12",
        rows=3,
        well_size_x=22.11,
        well_size_y=22.11,
        well_spacing_x=26.01,
        well_spacing_y=26.01,
    ),
    WellPlate(
        circular=True,
        cols=6,
        id="standard 24",
        rows=4,
        well_size_x=15.54,
        well_size_y=15.54,
        well_spacing_x=19.3,
        well_spacing_y=19.3,
    ),
    WellPlate(
        circular=False,
        cols=24,
        id="standard 384",
        rows=16,
        well_size_x=4.0,
        well_size_y=4.0,
        well_spacing_x=4.5,
        well_spacing_y=4.5,
    ),
    WellPlate(
        circular=True,
        cols=8,
        id="standard 48",
        rows=6,
        well_size_x=11.37,
        well_size_y=11.37,
        well_spacing_x=13.0,
        well_spacing_y=13.0,
    ),
    WellPlate(
        circular=True,
        cols=3,
        id="standard 6",
        rows=2,
        well_size_x=34.8,
        well_size_y=34.8,
        well_spacing_x=39.12,
        well_spacing_y=39.12,
    ),
    WellPlate(
        circular=True,
        cols=12,
        id="standard 96",
        rows=8,
        well_size_x=6.4,
        well_size_y=6.4,
        well_spacing_x=9.0,
        well_spacing_y=9.0,
    ),
]


PLATE_DB = {plate.id: plate for plate in sorted(PLATES, key=lambda p: p.id)}
