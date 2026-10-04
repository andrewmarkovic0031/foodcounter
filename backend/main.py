from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # swap for Alembic once the schema settles
    yield


app = FastAPI(title="Meal Tracker", lifespan=lifespan)
router = APIRouter(prefix="/api")  # the Vue app is served at /, the API lives under /api


# ---------- helpers ----------
def get_food_or_404(db: Session, food_id: int) -> models.Food:
    stmt = (
        select(models.Food)
        .where(models.Food.id == food_id)
        .options(
            selectinload(models.Food.ingredients).selectinload(
                models.FoodIngredient.ingredient
            )
        )
    )
    food = db.scalar(stmt)
    if not food:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Food not found")
    return food


def get_ingredient_or_404(db: Session, ingredient_id: int) -> models.Ingredient:
    ingredient = db.get(models.Ingredient, ingredient_id)
    if not ingredient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingredient not found")
    return ingredient


def get_meal_or_404(db: Session, meal_id: int) -> models.Meal:
    stmt = (
        select(models.Meal)
        .where(models.Meal.id == meal_id)
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
    db: Session, ingredients: list[schemas.FoodIngredientCreate]
) -> list[models.FoodIngredient]:
    ids = {item.ingredient_id for item in ingredients}
    found = set(
        db.scalars(select(models.Ingredient.id).where(models.Ingredient.id.in_(ids)))
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


def build_items(db: Session, items: list[schemas.MealItemCreate]) -> list[models.MealItem]:
    ids = {item.food_id for item in items}
    found = set(db.scalars(select(models.Food.id).where(models.Food.id.in_(ids))))
    missing = ids - found
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown food_id(s): {sorted(missing)}",
        )
    return [models.MealItem(food_id=item.food_id, quantity=item.quantity) for item in items]


# ---------- ingredients ----------
@router.post(
    "/ingredients",
    response_model=schemas.IngredientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ingredient(payload: schemas.IngredientCreate, db: Session = Depends(get_db)):
    ingredient = models.Ingredient(**payload.model_dump())
    db.add(ingredient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An ingredient with that name already exists"
        )
    db.refresh(ingredient)
    return ingredient


@router.get("/ingredients", response_model=list[schemas.IngredientRead])
def list_ingredients(
    q: str | None = Query(default=None, description="Substring match on name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = (
        select(models.Ingredient)
        .order_by(models.Ingredient.name)
        .limit(limit)
        .offset(offset)
    )
    if q:
        stmt = stmt.where(models.Ingredient.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.get("/ingredients/{ingredient_id}", response_model=schemas.IngredientRead)
def read_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    return get_ingredient_or_404(db, ingredient_id)


@router.patch("/ingredients/{ingredient_id}", response_model=schemas.IngredientRead)
def update_ingredient(
    ingredient_id: int,
    payload: schemas.IngredientUpdate,
    db: Session = Depends(get_db),
):
    ingredient = get_ingredient_or_404(db, ingredient_id)
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
            status.HTTP_409_CONFLICT, "An ingredient with that name already exists"
        )
    db.refresh(ingredient)
    return ingredient


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    ingredient = get_ingredient_or_404(db, ingredient_id)
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
def create_food(payload: schemas.FoodCreate, db: Session = Depends(get_db)):
    food = models.Food(
        name=payload.name,
        servings=payload.servings,
        ingredients=build_food_ingredients(db, payload.ingredients),
    )
    db.add(food)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A food with that name already exists")
    return get_food_or_404(db, food.id)


@router.get("/foods", response_model=list[schemas.FoodRead])
def list_foods(
    q: str | None = Query(default=None, description="Substring match on name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = (
        select(models.Food)
        .options(
            selectinload(models.Food.ingredients).selectinload(
                models.FoodIngredient.ingredient
            )
        )
        .order_by(models.Food.name)
        .limit(limit)
        .offset(offset)
    )
    if q:
        stmt = stmt.where(models.Food.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.get("/foods/{food_id}", response_model=schemas.FoodRead)
def read_food(food_id: int, db: Session = Depends(get_db)):
    return get_food_or_404(db, food_id)


@router.patch("/foods/{food_id}", response_model=schemas.FoodRead)
def update_food(food_id: int, payload: schemas.FoodUpdate, db: Session = Depends(get_db)):
    food = get_food_or_404(db, food_id)
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
        requested = build_food_ingredients(db, ingredients)
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
                models.Food.id != food_id,
            )
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "A food with that name already exists"
            )
        raise
    return get_food_or_404(db, food_id)


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food(food_id: int, db: Session = Depends(get_db)):
    food = get_food_or_404(db, food_id)
    db.delete(food)
    try:
        db.commit()
    except IntegrityError:  # still referenced by a meal (FK enforcement is on)
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Food is used in existing meals")


# ---------- meals ----------
@router.post("/meals", response_model=schemas.MealRead, status_code=status.HTTP_201_CREATED)
def create_meal(payload: schemas.MealCreate, db: Session = Depends(get_db)):
    meal = models.Meal(
        meal_type=payload.meal_type,
        notes=payload.notes,
        items=build_items(db, payload.items),
    )
    if payload.eaten_at:
        meal.eaten_at = payload.eaten_at
    db.add(meal)
    db.commit()
    return get_meal_or_404(db, meal.id)


@router.get("/meals", response_model=list[schemas.MealRead])
def list_meals(
    day: date | None = Query(default=None, description="Only meals eaten on this date"),
    meal_type: schemas.MealType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = (
        select(models.Meal)
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
def read_meal(meal_id: int, db: Session = Depends(get_db)):
    return get_meal_or_404(db, meal_id)


@router.patch("/meals/{meal_id}", response_model=schemas.MealRead)
def update_meal(meal_id: int, payload: schemas.MealUpdate, db: Session = Depends(get_db)):
    meal = get_meal_or_404(db, meal_id)
    data = payload.model_dump(exclude_unset=True)
    data.pop("items", None)  # items are handled separately below
    for key, value in data.items():
        setattr(meal, key, value)
    if payload.items is not None:
        meal.items = build_items(db, payload.items)  # delete-orphan removes the old ones
    db.commit()
    return get_meal_or_404(db, meal_id)


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = get_meal_or_404(db, meal_id)
    db.delete(meal)
    db.commit()


# ---------- summary ----------
@router.get("/profile/goals", response_model=schemas.ProfileGoalsRead)
def read_profile_goals(db: Session = Depends(get_db)):
    goals = db.get(models.ProfileGoals, 1)
    if goals is None:
        goals = models.ProfileGoals(id=1)
        db.add(goals)
        db.commit()
        db.refresh(goals)
    return goals


@router.put("/profile/goals", response_model=schemas.ProfileGoalsRead)
def update_profile_goals(
    payload: schemas.ProfileGoalsData, db: Session = Depends(get_db)
):
    goals = db.get(models.ProfileGoals, 1)
    if goals is None:
        goals = models.ProfileGoals(id=1)
        db.add(goals)
    for key, value in payload.model_dump().items():
        setattr(goals, key, value)
    db.commit()
    db.refresh(goals)
    return goals


@router.get("/profile/theme", response_model=schemas.ProfileThemeRead)
def read_profile_theme(db: Session = Depends(get_db)):
    theme = db.get(models.ProfileTheme, 1)
    if theme is None:
        theme = models.ProfileTheme(id=1)
        db.add(theme)
        db.commit()
        db.refresh(theme)
    return theme


@router.put("/profile/theme", response_model=schemas.ProfileThemeRead)
def update_profile_theme(
    payload: schemas.ProfileThemeData, db: Session = Depends(get_db)
):
    theme = db.get(models.ProfileTheme, 1)
    if theme is None:
        theme = models.ProfileTheme(id=1)
        db.add(theme)
    theme.accent_color = payload.accent_color
    db.commit()
    db.refresh(theme)
    return theme


@router.get("/summary/daily", response_model=schemas.DailySummary)
def daily_summary(day: date = Query(default_factory=date.today), db: Session = Depends(get_db)):
    start = datetime.combine(day, time.min)
    stmt = (
        select(models.Meal)
        .where(models.Meal.eaten_at >= start, models.Meal.eaten_at < start + timedelta(days=1))
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