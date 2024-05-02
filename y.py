import numpy as np
import xarray as xr
import zarr
from zarr.storage import KVStore

# Create an in-memory store
memory_store = KVStore({})

# Create some data
data = np.random.randn(3, 2, 512, 512)  # Shape corresponding to (t, c, y, x)

# Create a Zarr group in the memory store
root = zarr.group(store=memory_store, overwrite=True)

# Add dimensions and coordinates
t = np.array([0, 1, 2])  # Time coordinates
c = np.array(["DAPI", "FITC"])  # Channel labels

# Create the dataset within the group
dset = root.create_dataset("data", data=data, chunks=(1, 1, 256, 256), dtype="float32")

# Add attributes for xarray compatibility
dset.attrs["_ARRAY_DIMENSIONS"] = ["t", "c", "y", "x"]

# Create coordinate datasets
root["t"] = t
# root['c'] = c
root["t"].attrs["_ARRAY_DIMENSIONS"] = ["t"]
# root['c'].attrs['_ARRAY_DIMENSIONS'] = ['c']

# Open the Zarr group with xarray directly using the in-memory store
ds = xr.open_zarr(memory_store, consolidated=False)

# Print the xarray dataset
print(ds["data"])
