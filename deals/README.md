# deals/

Not where live deals go. Live client work lives in the data folder outside the repository
(`BIZWAVE_DATA_DIR`, default `C:\Users\<you>\BizWaveData` or `~/BizWaveData`), and the app refuses a
data folder inside the repository (`config.ensure_data_dirs`).

This folder stays git-ignored as a safety net: if a client file ever lands here by mistake, it still
cannot be committed. Tests use synthetic data only.
