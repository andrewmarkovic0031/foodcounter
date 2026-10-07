from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from loguru import logger

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from auth import get_current_user
from database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        raise RuntimeError("The library ownership migration currently requires SQLite.")
    with engine.begin() as connection:
        user_columns = {column["name"] for column in inspect(connection).get_columns("users")}
        for column, sql_type in (
            ("name", "VARCHAR(100)"),
            ("share_foods", "BOOLEAN NOT NULL DEFAULT 0"),
            ("share_ingredients", "BOOLEAN NOT NULL DEFAULT 0"),
            ("see_shared_foods", "BOOLEAN NOT NULL DEFAULT 0"),
            ("see_shared_ingredients", "BOOLEAN NOT NULL DEFAULT 0"),
        ):
            if column not in user_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column} {sql_type}"))

    _migrate_user_owned_data()
    _migrate_profile_preferences()
    yield


def _migrate_profile_preferences() -> None:
    raw_connection = engine.raw_connection()
    cursor = raw_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("BEGIN")
        tables = {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in ("profile_goals", "profile_theme"):
            if table not in tables:
                continue
            columns = {
                row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
            }
            legacy_table = f"legacy_{table}"
            if "user_id" not in columns:
                if legacy_table in tables:
                    raise RuntimeError(
                        f"Both {table} and {legacy_table} exist; resolve this migration manually."
                    )
                cursor.execute(f"ALTER TABLE {table} RENAME TO {legacy_table}")
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        raw_connection.close()

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        first_user_id = connection.execute(
            select(models.User.id).order_by(models.User.id).limit(1)
        ).scalar_one_or_none()
        if first_user_id is None:
            return
        for table, columns in (
            (
                "profile_goals",
                "kilojoules, protein, carbohydrates, fat, sugar",
            ),
            ("profile_theme", "accent_color"),
        ):
            legacy_table = f"legacy_{table}"
            legacy_exists = connection.scalar(
                text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :name"),
                {"name": legacy_table},
            )
            if legacy_exists:
                connection.execute(
                    text(
                        f"INSERT OR IGNORE INTO {table} (user_id, {columns}) "
                        f"SELECT :user_id, {columns} FROM {legacy_table} LIMIT 1"
                    ),
                    {"user_id": first_user_id},
                )
                connection.execute(text(f"DROP TABLE {legacy_table}"))


def _migrate_user_owned_data() -> None:
    raw_connection = engine.raw_connection()
    cursor = raw_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("BEGIN")
        for table, columns, create_sql in (
            (
                "ingredients",
                "id, name, kilojoules_per_100g, protein_per_100g, carbohydrates_per_100g, sugar_per_100g, fat_per_100g",
                """CREATE TABLE ingredients_new (
                    id INTEGER PRIMARY KEY,
                    owner_id INTEGER REFERENCES users(id),
                    name VARCHAR(100) NOT NULL,
                    kilojoules_per_100g FLOAT,
                    protein_per_100g FLOAT,
                    carbohydrates_per_100g FLOAT,
                    sugar_per_100g FLOAT,
                    fat_per_100g FLOAT,
                    CONSTRAINT uq_ingredient_owner_name UNIQUE (owner_id, name)
                )""",
            ),
            (
                "foods",
                "id, name, servings",
                """CREATE TABLE foods_new (
                    id INTEGER PRIMARY KEY,
                    owner_id INTEGER REFERENCES users(id),
                    name VARCHAR(100) NOT NULL,
                    servings FLOAT NOT NULL,
                    CONSTRAINT uq_food_owner_name UNIQUE (owner_id, name)
                )""",
            ),
            (
                "meals",
                "id, eaten_at, meal_type, notes",
                """CREATE TABLE meals_new (
                    id INTEGER PRIMARY KEY,
                    owner_id INTEGER REFERENCES users(id),
                    eaten_at DATETIME NOT NULL,
                    meal_type VARCHAR(20) NOT NULL,
                    notes TEXT
                )""",
            ),
        ):
            table_columns = {
                row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if "owner_id" not in table_columns:
                cursor.execute(f"DROP TABLE IF EXISTS {table}_new")
                cursor.execute(create_sql)
                cursor.execute(
                    f"INSERT INTO {table}_new ({columns}) SELECT {columns} FROM {table}"
                )
                cursor.execute(f"DROP TABLE {table}")
                cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_owner_id ON {table} (owner_id)"
            )
            if table == "meals":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ix_meals_eaten_at ON meals (eaten_at)"
                )

        first_user_id = cursor.execute("SELECT MIN(id) FROM users").fetchone()[0]
        if first_user_id is not None:
            cursor.execute(
                "UPDATE ingredients SET owner_id = ? WHERE owner_id IS NULL",
                (first_user_id,),
            )
            cursor.execute(
                "UPDATE foods SET owner_id = ? WHERE owner_id IS NULL",
                (first_user_id,),
            )
            cursor.execute(
                "UPDATE meals SET owner_id = ? WHERE owner_id IS NULL",
                (first_user_id,),
            )
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        raw_connection.close()


app = FastAPI(title="Meal Tracker", lifespan=lifespan)
router = APIRouter(
    prefix="/api",
    dependencies=[Depends(get_current_user)],
)  # the Vue app is served at /, the API lives under /api

USDA_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_NUTRIENTS = {
    "kilojoules_per_100g": (1062, 2048, 2047, 1008),
    "protein_per_100g": (1003,),
    "carbohydrates_per_100g": (1005,),
    "sugar_per_100g": (1063, 2000,),
    "fat_per_100g": (1004,),
}


# ---------- helpers ----------
def usda_nutrients(food: dict) -> dict[str, float | None]:
    nutrient_values: dict[int, float] = {}
    for nutrient in food.get("foodNutrients", []):
        nutrient_id = nutrient.get("nutrientId")
        if nutrient_id is None and isinstance(nutrient.get("nutrient"), dict):
            nutrient_id = nutrient["nutrient"].get("id")
        if nutrient_id is None:
            continue
        amount = nutrient.get("value", nutrient.get("amount"))
        if amount is not None:
            nutrient_values[int(nutrient_id)] = float(amount)

    result: dict[str, float | None] = {}
    for field, nutrient_ids in USDA_NUTRIENTS.items():
        value = next(
            (nutrient_values[nutrient_id] for nutrient_id in nutrient_ids
             if nutrient_id in nutrient_values),
            None,
        )
        if field == "kilojoules_per_100g" and value is not None:
            selected_id = next(nutrient_id for nutrient_id in nutrient_ids if nutrient_id in nutrient_values)
            if selected_id != 1062:
                value *= 4.184
        result[field] = value
    return result


def search_usda_foods(query: str, limit: int) -> list[dict]:
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "USDA search is not configured. Set USDA_API_KEY on the backend.",
        )

    request = Request(
        f"{USDA_API_URL}?{urlencode({'api_key': api_key})}",
        data=json.dumps(
            {
                "query": query,
                "pageSize": limit,
                "dataType": ["Foundation"],
            }
        ).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
    except HTTPError as error:
        if error.code == 429:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "USDA search rate limit reached. Try again later.",
            ) from error
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"USDA search failed with status {error.code}.",
        ) from error
    except (URLError, TimeoutError) as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Could not reach USDA FoodData Central."
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "USDA returned an invalid search response."
        ) from error

    foods = payload.get("foods") if isinstance(payload, dict) else None
    if not isinstance(foods, list):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "USDA returned an invalid search response."
        )

    results = []
    for food in foods:
        if not isinstance(food, dict) or not food.get("description"):
            continue
        results.append(
            {
                "fdc_id": food["fdcId"],
                "description": food["description"],
                "data_type": food.get("dataType"),
                "brand_owner": food.get("brandOwner"),
                **usda_nutrients(food),
            }
        )
    return results


def food_visibility_clause(current_user: models.User):
    if not current_user.see_shared_foods:
        return models.Food.owner_id == current_user.id
    return (
        (models.Food.owner_id == current_user.id)
        | select(models.User.id)
        .where(
            models.User.id == models.Food.owner_id,
            models.User.share_foods.is_(True),
        )
        .exists()
    )


def ingredient_visibility_clause(current_user: models.User):
    if not current_user.see_shared_ingredients:
        return models.Ingredient.owner_id == current_user.id
    return (
        (models.Ingredient.owner_id == current_user.id)
        | select(models.User.id)
        .where(
            models.User.id == models.Ingredient.owner_id,
            models.User.share_ingredients.is_(True),
        )
        .exists()
    )


def get_food_or_404(
    db: Session, food_id: int, current_user: models.User | None = None, *, owned: bool = False
) -> models.Food:
    stmt = (
        select(models.Food)
        .where(models.Food.id == food_id)
        .options(
            selectinload(models.Food.ingredients).selectinload(
                models.FoodIngredient.ingredient
            )
        )
    )
    if current_user is not None:
        stmt = stmt.where(
            models.Food.owner_id == current_user.id
            if owned
            else food_visibility_clause(current_user)
        )
    food = db.scalar(stmt)
    if not food:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Food not found")
    return food


def get_ingredient_or_404(
    db: Session, ingredient_id: int, current_user: models.User | None = None, *, owned: bool = False
) -> models.Ingredient:
    stmt = select(models.Ingredient).where(models.Ingredient.id == ingredient_id)
    if current_user is not None:
        stmt = stmt.where(
            models.Ingredient.owner_id == current_user.id
            if owned
            else ingredient_visibility_clause(current_user)
        )
    ingredient = db.scalar(stmt)
    if not ingredient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingredient not found")
    return ingredient


def get_meal_or_404(
    db: Session, meal_id: int, current_user: models.User
) -> models.Meal:
    stmt = (
        select(models.Meal)
        .where(models.Meal.id == meal_id, models.Meal.owner_id == current_user.id)
        .options(
            selectinload(models.Meal.items)
            .selectinload(models.MealItem.food)
            .selectinload(models.Food.ingredients)
            .selectinload(models.FoodIngredient.ingredient)
        )
        .execution_options(populate_existing=True)  # pick up changes after commit
    )
    meal = db.scalar(stmt)
    if not meal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meal not found")
    return meal


def build_food_ingredients(
    db: Session,
    ingredients: list[schemas.FoodIngredientCreate],
    current_user: models.User,
) -> list[models.FoodIngredient]:
    ids = {item.ingredient_id for item in ingredients}
    found = set(
        db.scalars(
            select(models.Ingredient.id)
            .where(models.Ingredient.id.in_(ids))
            .where(ingredient_visibility_clause(current_user))
        )
    )
    missing = ids - found
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown ingredient_id(s): {sorted(missing)}",
        )
    if len(ids) != len(ingredients):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Each ingredient can only be added once to a food",
        )
    return [
        models.FoodIngredient(ingredient_id=item.ingredient_id, grams=item.grams)
        for item in ingredients
    ]


def build_items(
    db: Session, items: list[schemas.MealItemCreate], current_user: models.User
) -> list[models.MealItem]:
    ids = {item.food_id for item in items}
    found = set(
        db.scalars(
            select(models.Food.id)
            .where(models.Food.id.in_(ids))
            .where(food_visibility_clause(current_user))
        )
    )
    missing = ids - found
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown food_id(s): {sorted(missing)}",
        )
    return [models.MealItem(food_id=item.food_id, quantity=item.quantity) for item in items]


# ---------- ingredients ----------
@router.get("/auth/me", response_model=schemas.CurrentUserRead)
def read_current_user(
    current_user: models.User = Depends(get_current_user),
):
    return current_user


@router.put("/auth/me", response_model=schemas.CurrentUserRead)
def update_current_user(
    payload: schemas.UserNameUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.name = payload.name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/auth/library-preferences", response_model=schemas.CurrentUserRead)
def update_library_preferences(
    payload: schemas.UserLibraryPreferences,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for key, value in payload.model_dump().items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get(
    "/ingredients/usda/search", response_model=list[schemas.USDAFoodSearchResult]
)
def search_ingredients_usda(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=10, ge=1, le=25),
):
    return search_usda_foods(q, limit)


@router.post(
    "/ingredients",
    response_model=schemas.IngredientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ingredient(
    payload: schemas.IngredientCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ingredient = models.Ingredient(owner_id=current_user.id, **payload.model_dump())
    db.add(ingredient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have an ingredient with that name"
        )
    db.refresh(ingredient)
    return ingredient


@router.get("/ingredients", response_model=list[schemas.IngredientRead])
def list_ingredients(
    q: str | None = Query(default=None, description="Substring match on name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(models.Ingredient)
        .where(ingredient_visibility_clause(current_user))
        .order_by(models.Ingredient.name)
        .limit(limit)
        .offset(offset)
    )
    if q:
        stmt = stmt.where(models.Ingredient.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.get("/ingredients/{ingredient_id}", response_model=schemas.IngredientRead)
def read_ingredient(
    ingredient_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_ingredient_or_404(db, ingredient_id, current_user)


@router.patch("/ingredients/{ingredient_id}", response_model=schemas.IngredientRead)
def update_ingredient(
    ingredient_id: int,
    payload: schemas.IngredientUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ingredient = get_ingredient_or_404(db, ingredient_id, current_user, owned=True)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name cannot be null")
    for key, value in data.items():
        setattr(ingredient, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have an ingredient with that name"
        )
    db.refresh(ingredient)
    return ingredient


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(
    ingredient_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ingredient = get_ingredient_or_404(db, ingredient_id, current_user, owned=True)
    db.delete(ingredient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ingredient is used in existing foods"
        )


# ---------- foods ----------
@router.post("/foods", response_model=schemas.FoodRead, status_code=status.HTTP_201_CREATED)
def create_food(
    payload: schemas.FoodCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    food = models.Food(
        owner_id=current_user.id,
        name=payload.name,
        servings=payload.servings,
        ingredients=build_food_ingredients(db, payload.ingredients, current_user),
    )
    db.add(food)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a food with that name")
    return get_food_or_404(db, food.id, current_user)


@router.get("/foods", response_model=list[schemas.FoodRead])
def list_foods(
    q: str | None = Query(default=None, description="Substring match on name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(models.Food)
        .options(
            selectinload(models.Food.ingredients).selectinload(
                models.FoodIngredient.ingredient
            )
        )
        .where(food_visibility_clause(current_user))
        .order_by(models.Food.name)
        .limit(limit)
        .offset(offset)
    )
    if q:
        stmt = stmt.where(models.Food.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.get("/foods/{food_id}", response_model=schemas.FoodRead)
def read_food(
    food_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_food_or_404(db, food_id, current_user)


@router.patch("/foods/{food_id}", response_model=schemas.FoodRead)
def update_food(
    food_id: int,
    payload: schemas.FoodUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    food = get_food_or_404(db, food_id, current_user, owned=True)
    data = payload.model_dump(exclude_unset=True)
    ingredients = payload.ingredients
    ingredients_was_provided = "ingredients" in payload.model_fields_set
    data.pop("ingredients", None)
    if "name" in data and data["name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name cannot be null")
    if "servings" in data and data["servings"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Servings cannot be null"
        )
    for key, value in data.items():
        setattr(food, key, value)
    if ingredients_was_provided:
        if ingredients is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Ingredients cannot be null"
            )
        requested = build_food_ingredients(db, ingredients, current_user)
        existing = {item.ingredient_id: item for item in food.ingredients}
        updated_ingredients = []
        for requested_item in requested:
            current = existing.get(requested_item.ingredient_id)
            if current is None:
                current = requested_item
            else:
                current.grams = requested_item.grams
            updated_ingredients.append(current)
        food.ingredients = updated_ingredients
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if "name" in data and db.scalar(
            select(models.Food.id).where(
                models.Food.name == data["name"],
                models.Food.owner_id == current_user.id,
                models.Food.id != food_id,
            )
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "A food with that name already exists"
            )
        raise
    return get_food_or_404(db, food_id, current_user)


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(
    food_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    food = get_food_or_404(db, food_id, current_user, owned=True)
    db.delete(food)
    try:
        db.commit()
    except IntegrityError:  # still referenced by a meal (FK enforcement is on)
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Food is used in existing meals")


# ---------- meals ----------
@router.post("/meals", response_model=schemas.MealRead, status_code=status.HTTP_201_CREATED)
def create_meal(
    payload: schemas.MealCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meal = models.Meal(
        owner_id=current_user.id,
        meal_type=payload.meal_type,
        notes=payload.notes,
        items=build_items(db, payload.items, current_user),
    )
    if payload.eaten_at:
        meal.eaten_at = payload.eaten_at
    db.add(meal)
    db.commit()
    return get_meal_or_404(db, meal.id, current_user)


@router.get("/meals", response_model=list[schemas.MealRead])
def list_meals(
    day: date | None = Query(default=None, description="Only meals eaten on this date"),
    meal_type: schemas.MealType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(models.Meal)
        .where(models.Meal.owner_id == current_user.id)
        .options(selectinload(models.Meal.items).selectinload(models.MealItem.food))
        .order_by(models.Meal.eaten_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if day:
        start = datetime.combine(day, time.min)
        stmt = stmt.where(models.Meal.eaten_at >= start, models.Meal.eaten_at < start + timedelta(days=1))
    if meal_type:
        stmt = stmt.where(models.Meal.meal_type == meal_type)
    return db.scalars(stmt).all()


@router.get("/meals/{meal_id}", response_model=schemas.MealRead)
def read_meal(
    meal_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_meal_or_404(db, meal_id, current_user)


@router.patch("/meals/{meal_id}", response_model=schemas.MealRead)
def update_meal(
    meal_id: int,
    payload: schemas.MealUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meal = get_meal_or_404(db, meal_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    data.pop("items", None)  # items are handled separately below
    for key, value in data.items():
        setattr(meal, key, value)
    if payload.items is not None:
        meal.items = build_items(db, payload.items, current_user)  # delete-orphan removes the old ones
    db.commit()
    return get_meal_or_404(db, meal_id, current_user)


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
    meal_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meal = get_meal_or_404(db, meal_id, current_user)
    db.delete(meal)
    db.commit()


# ---------- summary ----------
@router.get("/profile/goals", response_model=schemas.ProfileGoalsRead)
def read_profile_goals(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goals = db.get(models.ProfileGoals, current_user.id)
    if goals is None:
        goals = models.ProfileGoals(user_id=current_user.id)
        db.add(goals)
        db.commit()
        db.refresh(goals)
    return goals


@router.put("/profile/goals", response_model=schemas.ProfileGoalsRead)
def update_profile_goals(
    payload: schemas.ProfileGoalsData,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goals = db.get(models.ProfileGoals, current_user.id)
    if goals is None:
        goals = models.ProfileGoals(user_id=current_user.id)
        db.add(goals)
    for key, value in payload.model_dump().items():
        setattr(goals, key, value)
    db.commit()
    db.refresh(goals)
    return goals


@router.get("/profile/theme", response_model=schemas.ProfileThemeRead)
def read_profile_theme(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    theme = db.get(models.ProfileTheme, current_user.id)
    if theme is None:
        theme = models.ProfileTheme(user_id=current_user.id)
        db.add(theme)
        db.commit()
        db.refresh(theme)
    return theme


@router.put("/profile/theme", response_model=schemas.ProfileThemeRead)
def update_profile_theme(
    payload: schemas.ProfileThemeData,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    theme = db.get(models.ProfileTheme, current_user.id)
    if theme is None:
        theme = models.ProfileTheme(user_id=current_user.id)
        db.add(theme)
    theme.accent_color = payload.accent_color
    db.commit()
    db.refresh(theme)
    return theme


@router.get("/summary/daily", response_model=schemas.DailySummary)
def daily_summary(
    day: date = Query(default_factory=date.today),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start = datetime.combine(day, time.min)
    stmt = (
        select(models.Meal)
        .where(
            models.Meal.owner_id == current_user.id,
            models.Meal.eaten_at >= start,
            models.Meal.eaten_at < start + timedelta(days=1),
        )
        .options(selectinload(models.Meal.items).selectinload(models.MealItem.food))
    )
    meals = db.scalars(stmt).all()
    totals = {"kilojoules": 0.0, "protein": 0.0, "carbohydrates": 0.0, "fat": 0.0, "sugar": 0.0}
    for meal in meals:
        for item in meal.items:
            for key in totals:
                totals[key] += (
                    item.food.nutrition_per_serving(key) or 0
                ) * item.quantity
    return schemas.DailySummary(date=day.isoformat(), meals=len(meals), **totals)


app.include_router(router)

# Serve the built Vue app (run `npm run build` in frontend/) from the same origin as the API.
# This must come last so it never shadows the /api routes.
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")