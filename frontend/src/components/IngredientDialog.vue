<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { api } from '../api'
import { foodsChanged, loadFoods, loadIngredients, store } from '../foods'
import { notify } from '../ui'
import { trackVisualViewport } from '../visualViewport'
import { formatEnergy } from '../nutrition'

const el = ref(null)
const nameInput = ref(null)
const editing = ref(null)
const error = ref('')
const busy = ref(false)
const readOnly = computed(
  () => editing.value !== null && editing.value.owner_id !== store.userId
)
const mode = ref('manual')
const searchQuery = ref('')
const searchResults = ref([])
const catalogResults = ref([])
const searching = ref(false)
let stopViewportTracking = null
const form = reactive({
  name: '',
  kilojoules_per_100g: '',
  protein_per_100g: '',
  carbohydrates_per_100g: '',
  fat_per_100g: '',
  sugar_per_100g: ''
})

const nutrients = [
  ['kilojoules_per_100g', 'Kilojoules', 'kJ'],
  ['protein_per_100g', 'Protein', 'g'],
  ['carbohydrates_per_100g', 'Carbohydrates', 'g'],
  ['fat_per_100g', 'Fat', 'g'],
  ['sugar_per_100g', 'Sugar', 'g']
]

const show = (value) => (value == null ? '' : value)
const toNum = (value) => (value === '' || value == null ? null : Number(value))

async function open(ingredient = null) {
  editing.value = ingredient
  mode.value = 'manual'
  error.value = ''
  searchQuery.value = ''
  searchResults.value = []
  catalogResults.value = []
  form.name = ingredient?.name ?? ''
  for (const [field] of nutrients) form[field] = show(ingredient?.[field])
  await nextTick()
  el.value.showModal()
  stopViewportTracking?.()
  stopViewportTracking = trackVisualViewport(el.value)
  if (!ingredient) nameInput.value?.focus()
}

function onClose() {
  stopViewportTracking?.()
  stopViewportTracking = null
}

async function searchUSDA() {
  error.value = ''
  searchResults.value = []
  const query = searchQuery.value.trim()
  if (query.length < 2) {
    error.value = 'Enter at least two characters to search USDA.'
    return
  }

  searching.value = true
  try {
    searchResults.value = await api.searchUSDAIngredients(query)
    if (!searchResults.value.length) error.value = 'No matching USDA foods found.'
  } catch (e) {
    error.value = e.message
  } finally {
    searching.value = false
  }
}

async function searchCatalog() {
  error.value = ''
  catalogResults.value = []
  const query = searchQuery.value.trim()
  if (query.length < 2) {
    error.value = 'Enter at least two characters to search the local catalogue.'
    return
  }

  searching.value = true
  try {
    catalogResults.value = await api.searchIngredientCatalog(query)
    if (!catalogResults.value.length) error.value = 'No matching catalogue items found.'
  } catch (e) {
    error.value = e.message
  } finally {
    searching.value = false
  }
}

async function addCatalogIngredient(result) {
  error.value = ''
  busy.value = true
  try {
    await api.addCatalogIngredient(result.id)
    await refreshCatalogs()
    el.value.close()
    notify(result.already_added ? 'Ingredient updated from catalogue' : 'Ingredient added')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function addUSDAIngredient(result) {
  error.value = ''
  if (result.description.length > 100) {
    error.value = 'This USDA name is longer than 100 characters and cannot be added.'
    return
  }
  busy.value = true
  try {
    await api.createIngredient({
      name: result.description,
      kilojoules_per_100g: result.kilojoules_per_100g,
      protein_per_100g: result.protein_per_100g,
      carbohydrates_per_100g: result.carbohydrates_per_100g,
      sugar_per_100g: result.sugar_per_100g,
      fat_per_100g: result.fat_per_100g
    })
    await refreshCatalogs()
    el.value.close()
    notify('USDA ingredient added')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function refreshCatalogs() {
  await Promise.all([loadIngredients(), loadFoods()])
  foodsChanged()
}

async function save() {
  if (readOnly.value) return
  error.value = ''
  const payload = { name: form.name.trim() }
  for (const [field] of nutrients) payload[field] = toNum(form[field])
  busy.value = true
  try {
    const wasEditing = editing.value !== null
    if (wasEditing) await api.updateIngredient(editing.value.id, payload)
    else await api.createIngredient(payload)
    await refreshCatalogs()
    el.value.close()
    notify(wasEditing ? 'Ingredient updated' : 'Ingredient added')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove() {
  if (readOnly.value) return
  busy.value = true
  try {
    await api.deleteIngredient(editing.value.id)
    await refreshCatalogs()
    el.value.close()
    notify('Ingredient deleted')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <dialog ref="el" class="sheet" aria-labelledby="ingredient-dialog-title" @close="onClose">
    <form class="sheet-body" @submit.prevent="save">
      <header class="sheet-head">
        <h2 id="ingredient-dialog-title">{{ editing ? 'Edit ingredient' : 'New ingredient' }}</h2>
        <button type="button" class="icon-btn" aria-label="Close" @click="el.close()">✕</button>
      </header>

      <div class="sheet-scroll">
        <p v-if="readOnly" class="muted">
          This ingredient is shared by another user and is read-only.
        </p>
        <fieldset :disabled="readOnly">
          <legend class="sr-only">Ingredient details</legend>
        <div v-if="!editing" class="seg-options" aria-label="Ingredient source">
          <button
            v-for="[value, label] in [['manual', 'Create manually'], ['catalog', 'Search catalogue'], ['usda', 'Search USDA']]"
            :key="value"
            type="button"
            class="btn"
            :class="{ secondary: mode !== value }"
            :aria-pressed="mode === value"
            @click="mode = value; error = ''; catalogResults = []; searchResults = []"
          >
            {{ label }}
          </button>
        </div>

        <template v-if="mode === 'manual'">
        <div class="field">
          <label for="ingredient-name">Name</label>
          <input
            id="ingredient-name"
            ref="nameInput"
            v-model="form.name"
            type="text"
            maxlength="100"
            required
          />
        </div>

        <p class="muted hint">Enter nutrition values for 100g of this ingredient.</p>

        <div class="grid2">
          <div v-for="[field, label, unit] in nutrients" :key="field" class="field">
            <label :for="`ingredient-${field}`">{{ label }}</label>
            <div class="input-unit">
              <input
                :id="`ingredient-${field}`"
                v-model.number="form[field]"
                class="unit-input"
                type="number"
                inputmode="decimal"
                min="0"
                step="any"
              />
              <span aria-hidden="true">{{ unit }}</span>
            </div>
          </div>
        </div>
        </template>

        <template v-else-if="mode === 'catalog'">
          <p class="muted">
            Search the local nutrition catalogue. Values are per 100 g. Selecting an item adds it to your ingredients;
            selecting it again refreshes it from the latest catalogue data.
          </p>
          <div class="usda-search">
            <div class="field grow">
              <label for="catalog-search-query">Item name</label>
              <input
                id="catalog-search-query"
                v-model="searchQuery"
                type="search"
                minlength="2"
                placeholder="Search catalogue"
                autocomplete="off"
                @keydown.enter.prevent="searchCatalog"
              />
            </div>
            <button type="button" class="btn secondary" :disabled="searching" @click="searchCatalog">
              {{ searching ? 'Searching…' : 'Search' }}
            </button>
          </div>

          <ul v-if="catalogResults.length" class="usda-results" aria-label="Local catalogue results">
            <li v-for="result in catalogResults" :key="result.id" class="card usda-result">
              <div class="usda-result-copy">
                <strong>{{ result.name }}</strong>
                <span class="muted">
                  {{ formatEnergy(result.kilojoules_per_100g) }}
                  · P {{ result.protein_per_100g ?? '–' }} g
                  · C {{ result.carbohydrates_per_100g ?? '–' }} g
                  · F {{ result.fat_per_100g ?? '–' }} g
                  · S {{ result.sugar_per_100g ?? '–' }} g
                </span>
              </div>
              <button type="button" class="btn" :disabled="busy" @click="addCatalogIngredient(result)">
                {{ result.already_added ? 'Update' : 'Add' }}
              </button>
            </li>
          </ul>
        </template>

        <template v-else>
          <p class="muted">
            Search USDA FoodData Central, then add a result to your ingredient list.
            Nutrition values are per 100 g.
          </p>
          <div class="usda-search">
            <div class="field grow">
              <label for="usda-search-query">Food name</label>
              <input
                id="usda-search-query"
                v-model="searchQuery"
                type="search"
                minlength="2"
                placeholder="e.g. rolled oats"
                autocomplete="off"
                @keydown.enter.prevent="searchUSDA"
              />
            </div>
            <button type="button" class="btn secondary" :disabled="searching" @click="searchUSDA">
              {{ searching ? 'Searching…' : 'Search' }}
            </button>
          </div>

          <ul v-if="searchResults.length" class="usda-results" aria-label="USDA search results">
            <li v-for="result in searchResults" :key="result.fdc_id" class="card usda-result">
              <div class="usda-result-copy">
                <strong>{{ result.description }}</strong>
                <span class="muted">
                  {{ result.data_type }}<template v-if="result.brand_owner"> · {{ result.brand_owner }}</template>
                </span>
                <span class="muted">
                  {{ formatEnergy(result.kilojoules_per_100g) }}
                  · P {{ result.protein_per_100g ?? '–' }} g
                  · C {{ result.carbohydrates_per_100g ?? '–' }} g
                  · F {{ result.fat_per_100g ?? '–' }} g
                  · S {{ result.sugar_per_100g ?? '–' }} g
                </span>
              </div>
              <button type="button" class="btn" :disabled="busy" @click="addUSDAIngredient(result)">
                Add
              </button>
            </li>
          </ul>
        </template>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
        </fieldset>
      </div>

      <footer class="sheet-foot">
        <button v-if="editing && !readOnly" type="button" class="btn danger" :disabled="busy" @click="remove">
          Delete
        </button>
        <button v-if="mode === 'manual' && !readOnly" type="submit" class="btn grow" :disabled="busy">
          {{ busy ? 'Saving…' : 'Save' }}
        </button>
        <p v-if="readOnly" class="muted">Only the owner can edit this ingredient.</p>
      </footer>
    </form>
  </dialog>
</template>
