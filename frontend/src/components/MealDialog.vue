<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { api } from '../api'
import { store } from '../foods'
import { pad, parseLocal, toLocalInput } from '../dates'
import { notify, openFoodDialog } from '../ui'
import { trackVisualViewport } from '../visualViewport'
import { formatEnergy } from '../nutrition'
import SearchableSelect from './SearchableSelect.vue'

const props = defineProps({ day: { type: String, required: true } })
const emit = defineEmits(['saved'])

const TYPES = [
  ['breakfast', 'Breakfast'],
  ['lunch', 'Lunch'],
  ['dinner', 'Dinner'],
  ['snack', 'Snack'],
]

const el = ref(null)
const editingId = ref(null)
const error = ref('')
const busy = ref(false)
let stopViewportTracking = null
const form = reactive({ meal_type: 'lunch', eaten_at: '', notes: '', rows: [] })

const foodOptions = computed(() =>
  store.foods.map((food) => ({
    id: food.id,
    label: `${food.name}${food.kilojoules != null ? ` · ${formatEnergy(food.kilojoules)}` : ''}`
  }))
)
let uid = 0
const newRow = (food_id = '', quantity = 1) => ({ key: ++uid, food_id, quantity })

function guessType(hour) {
  if (hour < 4) return 'snack'
  if (hour < 10) return 'breakfast'
  if (hour < 15) return 'lunch'
  if (hour < 21) return 'dinner'
  return 'snack'
}

async function open(meal = null) {
  error.value = ''
  editingId.value = meal?.id ?? null
  if (meal) {
    form.meal_type = meal.meal_type
    form.eaten_at = toLocalInput(parseLocal(meal.eaten_at))
    form.notes = meal.notes ?? ''
    form.rows = meal.items.map((i) => newRow(i.food.id, i.quantity))
  } else {
    const now = new Date()
    form.meal_type = guessType(now.getHours())
    // Current time of day, on whichever day is being viewed
    form.eaten_at = `${props.day}T${pad(now.getHours())}:${pad(now.getMinutes())}`
    form.notes = ''
    form.rows = [newRow()]
  }
  await nextTick() // let the form render with its new values before it appears
  el.value.showModal()
  stopViewportTracking?.()
  stopViewportTracking = trackVisualViewport(el.value)
}

function onClose() {
  stopViewportTracking?.()
  stopViewportTracking = null
}

function addNewFood() {
  openFoodDialog(null, (food) => {
    const empty = form.rows.find((r) => r.food_id === '')
    if (empty) empty.food_id = food.id
    else form.rows.push(newRow(food.id))
  })
}

async function save() {
  error.value = ''
  const items = form.rows
    .filter((r) => r.food_id !== '')
    .map((r) => ({ food_id: Number(r.food_id), quantity: Number(r.quantity) }))

  if (!items.length && !form.notes.trim()) {
    error.value = 'Add at least one food, or write a note.'
    return
  }
  if (items.some((i) => !(i.quantity > 0))) {
    error.value = 'Quantities must be greater than zero.'
    return
  }

  const payload = {
    meal_type: form.meal_type,
    // datetime-local gives "YYYY-MM-DDTHH:mm"; send it without a timezone, as stored
    eaten_at: form.eaten_at.length === 16 ? `${form.eaten_at}:00` : form.eaten_at,
    notes: form.notes.trim() || null,
    items,
  }

  busy.value = true
  try {
    const wasEditing = editingId.value !== null
    if (wasEditing) await api.updateMeal(editingId.value, payload)
    else await api.createMeal(payload)
    el.value.close()
    emit('saved', form.eaten_at.slice(0, 10))
    notify(wasEditing ? 'Meal updated' : 'Meal logged')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove() {
  busy.value = true
  try {
    await api.deleteMeal(editingId.value)
    el.value.close()
    emit('saved')
    notify('Meal deleted')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <dialog ref="el" class="sheet" aria-labelledby="meal-dialog-title" @close="onClose">
    <form class="sheet-body" @submit.prevent="save">
      <header class="sheet-head">
        <h2 id="meal-dialog-title">{{ editingId ? 'Edit meal' : 'Log a meal' }}</h2>
        <button type="button" class="icon-btn" aria-label="Close" @click="el.close()">✕</button>
      </header>

      <div class="sheet-scroll">
        <fieldset class="seg">
          <legend>Meal type</legend>
          <div class="seg-options">
            <label v-for="[value, label] in TYPES" :key="value">
              <input v-model="form.meal_type" type="radio" name="meal-type" :value="value" />
              <span>{{ label }}</span>
            </label>
          </div>
        </fieldset>

        <div class="field">
          <label for="meal-when">When</label>
          <input id="meal-when" v-model="form.eaten_at" type="datetime-local" required />
        </div>

        <fieldset>
          <legend>Foods and servings</legend>
          <p v-if="store.loaded && !store.foods.length" class="muted hint">
            You haven't added any foods yet. Use “New food” below to add your first one.
          </p>

          <div v-for="(row, idx) in form.rows" :key="row.key" class="item-row">
            <div class="field grow">
              <label :for="`food-${row.key}`" class="sr-only">Food {{ idx + 1 }}</label>
              <SearchableSelect
                v-model="row.food_id"
                :options="foodOptions"
                :label="`Food ${idx + 1}`"
                placeholder="Search foods…"
              />
            </div>
            <div class="field qty">
              <label :for="`qty-${row.key}`" class="sr-only">Servings of food {{ idx + 1 }}</label>
              <input
                :id="`qty-${row.key}`"
                v-model.number="row.quantity"
                type="number"
                inputmode="decimal"
                min="0.01"
                step="any"
                placeholder="1"
              />
            </div>
            <button
              type="button"
              class="icon-btn"
              :aria-label="`Remove food ${idx + 1}`"
              @click="form.rows.splice(idx, 1)"
            >
              ✕
            </button>
          </div>

          <div class="row-actions">
            <button type="button" class="btn secondary" @click="form.rows.push(newRow())">+ Add food</button>
            <button type="button" class="btn ghost" @click="addNewFood">New food…</button>
          </div>
        </fieldset>

        <div class="field">
          <label for="meal-notes">Notes (optional)</label>
          <textarea id="meal-notes" v-model="form.notes" rows="2"></textarea>
        </div>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </div>

      <footer class="sheet-foot">
        <button v-if="editingId" type="button" class="btn danger" :disabled="busy" @click="remove">Delete</button>
        <button type="submit" class="btn grow" :disabled="busy">{{ busy ? 'Saving…' : 'Save' }}</button>
      </footer>
    </form>
  </dialog>
</template>
