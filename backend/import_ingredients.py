"""Import CSV ingredients directly into one user's Meal Tracker library."""

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import models
from database import SessionLocal

NUTRIENTS = (
    "kilojoules_per_100g",
    "protein_per_100g",
    "carbohydrates_per_100g",
    "sugar_per_100g",
    "fat_per_100g",
)
CSV_COLUMNS = ("name", *NUTRIENTS)
@dataclass
class IngredientPayload:
    name: str
    kilojoules_per_100g: float | None
    protein_per_100g: float | None
    carbohydrates_per_100g: float | None
    sugar_per_100g: float | None
    fat_per_100g: float | None


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


def import_csv(
    csv_path: Path,
    owner_email: str,
) -> tuple[int, int, int]:
    imported = skipped = failed = 0

    with SessionLocal() as db, csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        users = db.scalars(
            select(models.User).where(func.lower(models.User.email) == owner_email.lower())
        ).all()
        if not users:
            raise ValueError(
                f"No app user found with email {owner_email!r}. They must sign in once first."
            )
        if len(users) > 1:
            raise ValueError(f"Multiple app users have email {owner_email!r}; cannot choose safely.")
        owner = users[0]
        existing_names = set(
            db.scalars(
                select(models.Ingredient.name).where(
                    models.Ingredient.owner_id == owner.id
                )
            )
        )

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

            db.add(models.Ingredient(owner_id=owner.id, **payload.__dict__))
            try:
                db.commit()
                existing_names.add(name)
                imported += 1
                print(f"row {reader.line_num}: imported {name!r} for {owner.email}")
            except IntegrityError:
                db.rollback()
                existing_names.add(name)
                skipped += 1
                print(f"row {reader.line_num}: skipped existing ingredient {name!r}")
            except SQLAlchemyError as error:
                db.rollback()
                print(
                    f"row {reader.line_num}: could not import {name!r}: {error}",
                    file=sys.stderr,
                )
                failed += 1

    return imported, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="CSV file with one ingredient per row")
    parser.add_argument(
        "--user-email",
        required=True,
        help="Email address of the app user who will own the imported ingredients",
    )
    args = parser.parse_args()

    try:
        imported, skipped, failed = import_csv(
            args.csv_file,
            args.user_email,
        )
    except (OSError, ValueError, SQLAlchemyError) as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Finished: {imported} imported, {skipped} skipped, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
