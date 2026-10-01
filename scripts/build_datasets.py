"""
One-off data preparation (run offline, NOT per request).

Turns the assessment CSV (no coordinates) into data/stations.csv (with lat/lng)
and writes a slim data/us_cities.csv used to resolve "City, ST" inputs.

    python scripts/build_datasets.py \
        --fuel-csv /path/to/fuel-prices-for-be-assessment.csv \
        --cities-csv data_raw/us_cities.csv

The cities file is the free kelvins/US-Cities-Database CSV
(https://github.com/kelvins/US-Cities-Database).

Cleaning rules
--------------
* Canadian provinces are dropped (assignment is USA only).
* Rows are deduplicated by OPIS Truckstop ID. The CSV repeats IDs with
  different prices; we keep the LOWEST price (the best deal a driver could get).
* Coordinates come from an offline join on normalised City + State
  (city-level accuracy, which is all the highway-exit addresses allow).
* Rows whose city cannot be matched are dropped and reported.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

CANADA = {"AB", "BC", "MB", "NB", "NS", "ON", "QC", "SK", "YT", "NL", "PE", "NT", "NU"}
ROOT = Path(__file__).resolve().parent.parent


def norm(name: str) -> str:
    s = str(name).lower().replace(".", "").strip()
    s = re.sub(r"^(saint|st)\b", "st", s)
    s = re.sub(r"^(fort|ft)\b", "fort", s)
    s = re.sub(r"^(mount|mt)\b", "mount", s)
    return re.sub(r"[^a-z0-9 ]", "", s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuel-csv", required=True)
    ap.add_argument("--cities-csv", required=True)
    args = ap.parse_args()

    cities = pd.read_csv(args.cities_csv)
    cities = cities.rename(columns={"CITY": "city", "STATE_CODE": "state",
                                    "LATITUDE": "lat", "LONGITUDE": "lng"})
    cities["name_norm"] = cities["city"].map(norm)
    cities = cities.drop_duplicates(["name_norm", "state"])  # keep first per key
    cities[["city", "state", "name_norm", "lat", "lng"]].to_csv(ROOT / "data/us_cities.csv", index=False)

    df = pd.read_csv(args.fuel_csv)
    raw_rows = len(df)
    df.columns = ["opis_id", "name", "address", "city", "state", "rack_id", "price"]
    for col in ("name", "address", "city", "state"):
        df[col] = df[col].astype(str).str.strip()
    df = df[~df["state"].isin(CANADA)]
    df = df[df["price"] > 0]

    # one row per truckstop: lowest price wins
    df = df.sort_values("price").drop_duplicates("opis_id", keep="first")
    df["name_norm"] = df["city"].map(norm)
    df = df.merge(cities[["name_norm", "state", "lat", "lng"]], on=["name_norm", "state"], how="left")
    unmatched = df["lat"].isna().sum()
    df = df.dropna(subset=["lat", "lng"])

    out = df[["opis_id", "name", "address", "city", "state", "lat", "lng", "price"]]
    out = out.sort_values("opis_id")
    out.to_csv(ROOT / "data/stations.csv", index=False)
    print(f"raw rows: {raw_rows}  ->  stations kept: {len(out)}  (unmatched city dropped: {unmatched})")


if __name__ == "__main__":
    main()
