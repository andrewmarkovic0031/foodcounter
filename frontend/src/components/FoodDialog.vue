<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { api } from '../api'
import { foodsChanged, loadFoods, store } from '../foods'
import { notify } from '../ui'
import { trackVisualViewport } from '../visualViewport'
import SearchableSelect from './SearchableSelect.vue'

const el = ref(null)
const nameInput = ref(null)
const editing = ref(null)
const error = ref('')
const busy = ref(false)
const form = reactive({ name: '', servings: 1, ingredients: [] })
let stopViewportTracking = null
let uid = 0

const ingredientOptions = computed(() =>
  store.ingredients.map((ingredient) => ({ id: ingredient.id, name: ingredient.name }))
)
const newRow = (ingredient_id = '', grams = 100) => ({
  key: ++uid,
  ingredient_id,
  grams
})
const show = (value) => (value == null ? '' : value)
const grams = (value) => Math.round(value * 10) / 10

async function open(food = null) {
  editing.value = food
  error.value = ''
  form.name = food?.name ?? ''
  form.servings = show(food?.servings) || 1
  form.ingredients = food
    ? food.ingredients.map((item) => newRow(item.ingredient.id, item.grams))
    : [newRow()]
  await nextTick()
  el.value.showModal()
  stopViewportTracking?.()
  stopViewportTracking = trackVisualViewport(el.value)
  if (!food) nameInput.value?.focus()
}

function onClose() {
  stopViewportTracking?.()
  stopViewportTracking = null
}

async function save() {
  error.value = ''
  const ingredients = form.ingredients
    .filter((row) => row.ingredient_id !== '')
    .map((row) => ({ ingredient_id: Number(row.ingredient_id), grams: Number(row.grams) }))

  if (!ingredients.length) {
    error.value = 'Add at least one ingredient.'
    return
  }
  if (ingredients.some((item) => !(item.grams > 0))) {
    error.value = 'Ingredient quantities must be greater than zero.'
    return
  }
  if (!(Number(form.servings) > 0)) {
    error.value = 'Recipe servings must be greater than zero.'
    return
  }

  const payload = {
    name: form.name.trim(),
    servings: Number(form.servings),
    ingredients
  }
  busy.value = true
  try {
    const wasEditing = editing.value !== null
    if (wasEditing) await api.updateFood(editing.value.id, payload)
    else await api.createFood(payload)
    await loadFoods()
    if (wasEditing) foodsChanged()
    el.value.close()
    notify(wasEditing ? 'Food updated' : 'Food added')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove() {
  busy.value = true
  try {
    await api.deleteFood(editing.value.id)
    await loadFoods()
    foodsChanged()
    el.value.close()
    notify('Food deleted')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <dialog ref="el" class="sheet" aria-labelledby="food-dialog-title" @close="onClose">
    <form class="sheet-body" @submit.prevent="save">
      <header class="sheet-head">
        <h2 id="food-dialog-title">{{ editing ? 'Edit food' : 'New food' }}</h2>
        <button type="button" class="icon-btn" aria-label="Close" @click="el.close()">✕</button>
      </header>

      <div class="sheet-scroll">
        <div class="field">
          <label for="food-name">Food name</label>
          <input id="food-name" ref="nameInput" v-model="form.name" type="text" maxlength="100" required />
        </div>

        <div class="field">
          <label for="food-servings">Recipe servings</label>
          <input
            id="food-servings"
            v-model.number="form.servings"
            type="number"
            inputmode="decimal"
            min="0.01"
            step="any"
            required
          />
          <span class="muted hint">Ingredient amounts are for the whole recipe. Nutrition is divided by servings.</span>
        </div>

        <fieldset>
          <legend>Ingredients and amounts</legend>
          <p v-if="store.ingredientsLoaded && !store.ingredients.length" class="muted hint">
            Add ingredients in the Ingredients tab before creating a food.
          </p>

          <div v-for="(row, idx) in form.ingredients" :key="row.key" class="item-row">
            <div class="field grow">
              <label :for="`food-ingredient-${row.key}`" class="sr-only">
                Ingredient {{ idx + 1 }}
              </label>
              <SearchableSelect
                v-model="row.ingredient_id"
                :options="ingredientOptions"
                :label="`Ingredient ${idx + 1}`"
                placeholder="Search ingredients…"
              />
            </div>
            <div class="field qty">
              <label :for="`food-grams-${row.key}`" class="sr-only">Grams of ingredient {{ idx + 1 }}</label>
              <div class="input-unit">
                <input
                  :id="`food-grams-${row.key}`"
                  v-model.number="row.grams"
                  class="unit-input"
                  type="number"
                  inputmode="decimal"
                  min="0.01"
                  step="any"
                />
                <span aria-hidden="true">g</span>
              </div>
            </div>
            <button
              type="button"
              class="icon-btn"
              :aria-label="`Remove ingredient ${idx + 1}`"
              @click="form.ingredients.splice(idx, 1)"
            >
              ✕
            </button>
          </div>

          <button type="button" class="btn secondary" @click="form.ingredients.push(newRow())">
            + Add ingredient
          </button>
        </fieldset>

        <p v-if="editing" class="muted hint">
          Per serving:
          {{ editing.kilojoules != null ? `${Math.round(editing.kilojoules)} kJ` : 'No kilojoules' }}
          · P {{ grams(editing.protein ?? 0) }} g · C {{ grams(editing.carbohydrates ?? 0) }} g
          · F {{ grams(editing.fat ?? 0) }} g · S {{ grams(editing.sugar ?? 0) }} g
        </p>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </div>

      <footer class="sheet-foot">
        <button v-if="editing" type="button" class="btn danger" :disabled="busy" @click="remove">Delete</button>
        <button type="submit" class="btn grow" :disabled="busy">
          {{ busy ? 'Saving…' : 'Save' }}
        </button>
      </footer>
    </form>
  </dialog>
</template>
