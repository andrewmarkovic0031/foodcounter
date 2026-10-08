from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_ingredient_owner_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_catalog_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredient_catalog.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    kilojoules_per_100g: Mapped[float | None]
    protein_per_100g: Mapped[float | None]
    carbohydrates_per_100g: Mapped[float | None]
    sugar_per_100g: Mapped[float | None]
    fat_per_100g: Mapped[float | None]

    food_usages: Mapped[list["FoodIngredient"]] = relationship(back_populates="ingredient")


class IngredientCatalog(Base):
    __tablename__ = "ingredient_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    kilojoules_per_100g: Mapped[float | None]
    protein_per_100g: Mapped[float | None]
    carbohydrates_per_100g: Mapped[float | None]
    sugar_per_100g: Mapped[float | None]
    fat_per_100g: Mapped[float | None]


class Food(Base):
    __tablename__ = "foods"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_food_owner_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    servings: Mapped[float] = mapped_column(default=1.0)
    ingredients: Mapped[list["FoodIngredient"]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )

    def nutrition_per_serving(self, nutrient: str) -> float | None:
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


class FoodIngredient(Base):
    __tablename__ = "food_ingredients"
    __table_args__ = (
        CheckConstraint("grams > 0", name="ck_food_ingredients_grams_positive"),
        UniqueConstraint("food_id", "ingredient_id", name="uq_food_ingredient"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    grams: Mapped[float] = mapped_column(Float)

    food: Mapped["Food"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="food_usages")


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    eaten_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    meal_type: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None]

    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    quantity: Mapped[float] = mapped_column(default=1.0)

    meal: Mapped["Meal"] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship()


class ProfileGoals(Base):
    __tablename__ = "profile_goals"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    kilojoules: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbohydrates: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugar: Mapped[float | None] = mapped_column(Float, nullable=True)


class ProfileTheme(Base):
    __tablename__ = "profile_theme"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    accent_color: Mapped[str] = mapped_column(String(20), default="violet")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    share_foods: Mapped[bool] = mapped_column(default=False)
    share_ingredients: Mapped[bool] = mapped_column(default=False)
    see_shared_foods: Mapped[bool] = mapped_column(default=False)
    see_shared_ingredients: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
