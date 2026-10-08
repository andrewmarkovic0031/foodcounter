"""Import or update the shared ingredient search catalogue from a CSV file."""

import argparse
import csv
import math
import re
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

import models
from database import Base, SessionLocal, engine

DEFAULT_COLUMNS = {
    "key": "public_food_key",
    "name": "name",
    "kilojoules_per_100g": "kilojoules_per_100g",
    "protein_per_100g": "protein_per_100g",
    "sugar_per_100g": "sugar_per_100g",
    "carbohydrates_per_100g": "carbs_per_100g",
    "fat_per_100g": "fat_per_100g",
}


def normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def cell_value(row: Sequence[str], indexes: dict[str, int], column: str) -> str | None:
    return row[indexes[column]] if indexes[column] < len(row) else None


def external_key(value: Any) -> str:
    if value is None:
        raise ValueError("key is required")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    result = str(value).strip()
    if not result:
        raise ValueError("key is required")
    if len(result) > 100:
        raise ValueError("key must be 100 characters or fewer")
    return result


def nutrient_value(value: Any, column: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        result = float(str(value).replace(",", "").strip())
    except ValueError as error:
        raise ValueError(f"{column} must be a number") from error
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{column} must be a finite non-negative number")
    return result


def import_csv(csv_path: Path, column_names: dict[str, str]) -> tuple[int, int, int]:
    Base.metadata.tables[models.IngredientCatalog.__tablename__].create(
        engine, checkfirst=True
    )
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = csv.reader(source)
        try:
            headers = next(rows)
        except StopIteration as error:
            raise ValueError("The CSV file is empty.") from error

        header_indexes = {
            normalize_header(header): index for index, header in enumerate(headers)
        }
        indexes: dict[str, int] = {}
        for field, requested_name in column_names.items():
            index = header_indexes.get(normalize_header(requested_name))
            if index is None:
                raise ValueError(
                    f"Column {requested_name!r} for {field} was not found "
                    "in the CSV header."
                )
            indexes[field] = index

        created = updated = failed = 0
        pending = 0
        with SessionLocal() as db:
            for row_number, row in enumerate(rows, start=2):
                if not row or all(not value.strip() for value in row):
                    continue
                try:
                    key = external_key(cell_value(row, indexes, "key"))
                    name_value = cell_value(row, indexes, "name")
                    name = str(name_value or "").strip()
                    if not name:
                        raise ValueError("name is required")
                    if len(name) > 100:
                        raise ValueError("name must be 100 characters or fewer")
                    nutrients = {
                        field: nutrient_value(
                            cell_value(row, indexes, field), column_names[field]
                        )
                        for field in (
                            "kilojoules_per_100g",
                            "protein_per_100g",
                            "carbohydrates_per_100g",
                            "sugar_per_100g",
                            "fat_per_100g",
                        )
                    }
                except ValueError as error:
                    print(f"row {row_number}: {error}", file=sys.stderr)
                    failed += 1
                    continue

                try:
                    with db.begin_nested():
                        item = db.scalar(
                            select(models.IngredientCatalog).where(
                                models.IngredientCatalog.external_key == key
                            )
                        )
                        is_new = item is None
                        if item is None:
                            item = models.IngredientCatalog(
                                external_key=key, name=name
                            )
                            db.add(item)
                        item.name = name
                        for field, value in nutrients.items():
                            setattr(item, field, value)
                        db.flush()
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                    pending += 1
                    if pending >= 250:
                        db.commit()
                        pending = 0
                except SQLAlchemyError as error:
                    print(
                        f"row {row_number}: could not save key {key!r}: {error}",
                        file=sys.stderr,
                    )
                    failed += 1
            db.commit()
    return created, updated, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="CSV file to import")
    for field, default in DEFAULT_COLUMNS.items():
        parser.add_argument(
            f"--{field.replace('_', '-')}-column",
            default=default,
            help=f"Header for {field} (default: {default})",
        )
    args = parser.parse_args()
    column_names = {
        field: getattr(args, f"{field}_column") for field in DEFAULT_COLUMNS
    }

    try:
        created, updated, failed = import_csv(args.csv_file, column_names)
    except (OSError, ValueError, SQLAlchemyError) as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Finished: {created} added, {updated} updated, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
