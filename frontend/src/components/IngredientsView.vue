<script setup>
import { computed, ref } from 'vue'
import { store } from '../foods'
import { openIngredientDialog } from '../ui'
import { formatEnergy } from '../nutrition'

const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q
    ? store.ingredients.filter((ingredient) => ingredient.name.toLowerCase().includes(q))
    : store.ingredients
})

const amount = (value) => (value == null ? '–' : `${Math.round(value * 10) / 10}`)
</script>

<template>
  <header class="page-head">
    <h1>Ingredients</h1>
    <p class="muted">Nutrition values are per 100 g.</p>
  </header>

  <div class="field">
    <label for="ingredient-search" class="sr-only">Search ingredients</label>
    <input
      id="ingredient-search"
      v-model="query"
      type="search"
      placeholder="Search ingredients"
      autocomplete="off"
    />
  </div>

  <section aria-label="Ingredient list">
    <p v-if="!store.ingredientsLoaded" class="muted">Loading…</p>
    <p v-else-if="!store.ingredients.length" class="card empty">
      No ingredients yet. Add the ingredients you use to build foods.
    </p>
    <p v-else-if="!filtered.length" class="card empty">No ingredients match “{{ query }}”.</p>
    <ul v-else class="food-list">
      <li v-for="ingredient in filtered" :key="ingredient.id">
        <button
          type="button"
          class="card food"
          @click="openIngredientDialog(ingredient)"
        >
          <span class="food-name"><span class="sr-only">Edit </span>{{ ingredient.name }}</span>
          <span class="muted">
            <span v-if="ingredient.owner_id !== store.userId">Shared · </span>
            {{ formatEnergy(ingredient.kilojoules_per_100g) }}
            · P {{ amount(ingredient.protein_per_100g) }}
            · C {{ amount(ingredient.carbohydrates_per_100g) }}
            · F {{ amount(ingredient.fat_per_100g) }}
            · S {{ amount(ingredient.sugar_per_100g) }} g
          </span>
        </button>
      </li>
    </ul>
  </section>

  <button type="button" class="btn fab" @click="openIngredientDialog()">+ New ingredient</button>
</template>
