"""Import one ingredient per row from a CSV file into the running Meal Tracker API."""

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NUTRIENTS = (
    "kilojoules_per_100g",
    "protein_per_100g",
    "carbohydrates_per_100g",
    "sugar_per_100g",
    "fat_per_100g",
)
CSV_COLUMNS = ("name", *NUTRIENTS)
PAGE_SIZE = 200


@dataclass
class IngredientPayload:
    name: str
    kilojoules_per_100g: float | None
    protein_per_100g: float | None
    carbohydrates_per_100g: float | None
    sugar_per_100g: float | None
    fat_per_100g: float | None


def request_json(
    url: str, method: str = "GET", body: dict[str, object] | None = None
) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read()) if response.status != 204 else None
    except HTTPError as error:
        try:
            detail = json.loads(error.read()).get("detail", str(error))
        except (json.JSONDecodeError, AttributeError):
            detail = str(error)
        return error.code, detail
    except URLError as error:
        raise RuntimeError(f"Cannot reach the API at {url}: {error.reason}") from error


def list_existing_names(api_url: str) -> set[str]:
    names: set[str] = set()
    offset = 0
    while True:
        query = urlencode({"limit": PAGE_SIZE, "offset": offset})
        status, ingredients = request_json(f"{api_url}/ingredients?{query}")
        if status != 200 or ingredients is None:
            raise RuntimeError(f"Could not list existing ingredients: {ingredients}")
        names.update(item["name"] for item in ingredients)
        if len(ingredients) < PAGE_SIZE:
            return names
        offset += PAGE_SIZE


def parse_row(
    row: Mapping[str | None, str | None], line_number: int
) -> IngredientPayload:
    name = (row.get("name") or "").strip()
    if not name:
        raise ValueError(f"row {line_number}: name is required")
    if len(name) > 100:
        raise ValueError(f"row {line_number}: name must be 100 characters or fewer")

    nutrients: dict[str, float | None] = {}
    for column in NUTRIENTS:
        raw_value = (row.get(column) or "").strip()
        if not raw_value:
            nutrients[column] = None
            continue
        try:
            value = float(raw_value)
        except ValueError as error:
            raise ValueError(f"row {line_number}: {column} must be a number") from error
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"row {line_number}: {column} must be a finite non-negative number")
        nutrients[column] = value
    return IngredientPayload(
        name=name,
        kilojoules_per_100g=nutrients["kilojoules_per_100g"],
        protein_per_100g=nutrients["protein_per_100g"],
        carbohydrates_per_100g=nutrients["carbohydrates_per_100g"],
        sugar_per_100g=nutrients["sugar_per_100g"],
        fat_per_100g=nutrients["fat_per_100g"],
    )


def import_csv(csv_path: Path, api_url: str) -> tuple[int, int, int]:
    existing_names = list_existing_names(api_url)
    imported = skipped = failed = 0

    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = set(reader.fieldnames or ())
        missing = set(CSV_COLUMNS) - headers
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            try:
                payload = parse_row(row, reader.line_num)
            except ValueError as error:
                print(error, file=sys.stderr)
                failed += 1
                continue

            name = payload.name
            if name in existing_names:
                print(f"row {reader.line_num}: skipped existing ingredient {name!r}")
                skipped += 1
                continue

            status, result = request_json(
                f"{api_url}/ingredients", "POST", asdict(payload)
            )
            if status == 201:
                existing_names.add(name)
                imported += 1
                print(f"row {reader.line_num}: imported {name!r}")
            elif status == 409:
                existing_names.add(name)
                skipped += 1
                print(f"row {reader.line_num}: skipped existing ingredient {name!r}")
            else:
                print(f"row {reader.line_num}: could not import {name!r}: {result}", file=sys.stderr)
                failed += 1

    return imported, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="CSV file with one ingredient per row")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/api",
        help="Meal Tracker API base URL (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        imported, skipped, failed = import_csv(args.csv_file, args.api_url.rstrip("/"))
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Finished: {imported} imported, {skipped} skipped, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
