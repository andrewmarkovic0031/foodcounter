<script setup>
import { nextTick, reactive, ref } from 'vue'
import { api } from '../api'
import { foodsChanged, loadFoods, loadIngredients } from '../foods'
import { notify } from '../ui'
import { trackVisualViewport } from '../visualViewport'

const el = ref(null)
const nameInput = ref(null)
const editing = ref(null)
const error = ref('')
const busy = ref(false)
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
  error.value = ''
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

async function refreshCatalogs() {
  await Promise.all([loadIngredients(), loadFoods()])
  foodsChanged()
}

async function save() {
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

        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </div>

      <footer class="sheet-foot">
        <button v-if="editing" type="button" class="btn danger" :disabled="busy" @click="remove">
          Delete
        </button>
        <button type="submit" class="btn grow" :disabled="busy">
          {{ busy ? 'Saving…' : 'Save' }}
        </button>
      </footer>
    </form>
  </dialog>
</template>
