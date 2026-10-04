from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

MealType = Literal["breakfast", "lunch", "dinner", "snack"]


# ---------- Ingredients ----------
class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kilojoules_per_100g: float | None = Field(default=None, ge=0)
    protein_per_100g: float | None = Field(default=None, ge=0)
    carbohydrates_per_100g: float | None = Field(default=None, ge=0)
    sugar_per_100g: float | None = Field(default=None, ge=0)
    fat_per_100g: float | None = Field(default=None, ge=0)


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    kilojoules_per_100g: float | None = Field(default=None, ge=0)
    protein_per_100g: float | None = Field(default=None, ge=0)
    carbohydrates_per_100g: float | None = Field(default=None, ge=0)
    sugar_per_100g: float | None = Field(default=None, ge=0)
    fat_per_100g: float | None = Field(default=None, ge=0)


class IngredientRead(IngredientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Foods ----------
class FoodIngredientCreate(BaseModel):
    ingredient_id: int
    grams: float = Field(gt=0)


class FoodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    servings: float = Field(default=1, gt=0)
    ingredients: list[FoodIngredientCreate] = Field(min_length=1)


class FoodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    servings: float | None = Field(default=None, gt=0)
    ingredients: list[FoodIngredientCreate] | None = Field(default=None, min_length=1)


class FoodIngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grams: float
    ingredient: IngredientRead


class FoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    servings: float
    ingredients: list[FoodIngredientRead]

    @computed_field
    @property
    def kilojoules(self) -> float | None:
        return self._nutrition_per_serving("kilojoules")

    @computed_field
    @property
    def protein(self) -> float | None:
        return self._nutrition_per_serving("protein")

    @computed_field
    @property
    def carbohydrates(self) -> float | None:
        return self._nutrition_per_serving("carbohydrates")

    @computed_field
    @property
    def sugar(self) -> float | None:
        return self._nutrition_per_serving("sugar")

    @computed_field
    @property
    def fat(self) -> float | None:
        return self._nutrition_per_serving("fat")

    def _nutrition_per_serving(self, nutrient: str) -> float | None:
        values = [
            getattr(item.ingredient, f"{nutrient}_per_100g")
            for item in self.ingredients
        ]
        if not any(value is not None for value in values):
            return None
        return sum(
            (value or 0) * item.grams / 100
            for item, value in zip(self.ingredients, values)
        ) / self.servings


# ---------- Meals ----------
class MealItemCreate(BaseModel):
    food_id: int
    quantity: float = Field(default=1.0, gt=0)


class MealItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quantity: float
    food: FoodRead


class MealCreate(BaseModel):
    eaten_at: datetime | None = None
    meal_type: MealType
    notes: str | None = None
    items: list[MealItemCreate] = []


class MealUpdate(BaseModel):
    eaten_at: datetime | None = None
    meal_type: MealType | None = None
    notes: str | None = None
    items: list[MealItemCreate] | None = None


class MealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    eaten_at: datetime
    meal_type: str
    notes: str | None
    items: list[MealItemRead]

    @computed_field
    @property
    def total_kilojoules(self) -> float:
        return sum((i.food.kilojoules or 0) * i.quantity for i in self.items)


# ---------- Summary ----------
class DailySummary(BaseModel):
    date: str
    meals: int
    kilojoules: float
    protein: float
    carbohydrates: float
    fat: float
    sugar: float


# ---------- Profile ----------
class ProfileGoalsData(BaseModel):
    kilojoules: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbohydrates: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    sugar: float | None = Field(default=None, ge=0)


class ProfileGoalsRead(ProfileGoalsData):
    model_config = ConfigDict(from_attributes=True)


AccentColor = Literal["violet", "blue", "teal", "amber", "rose"]


class ProfileThemeData(BaseModel):
    accent_color: AccentColor = "violet"


class ProfileThemeRead(ProfileThemeData):
    model_config = ConfigDict(from_attributes=True)
