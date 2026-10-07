<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { ACCENT_COLORS, applyAccentColor } from '../theme'
import { notify } from '../ui'

const fields = [
  ['kilojoules', 'Kilojoules', 'kJ'],
  ['protein', 'Protein', 'g'],
  ['carbohydrates', 'Carbohydrates', 'g'],
  ['fat', 'Fat', 'g'],
  ['sugar', 'Sugar', 'g']
]

const goals = reactive({
  kilojoules: '',
  protein: '',
  carbohydrates: '',
  fat: '',
  sugar: ''
})
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const accentColor = ref('violet')
const currentUser = ref(null)

onMounted(async () => {
  try {
    const [saved, theme, user] = await Promise.all([
      api.profileGoals(),
      api.profileTheme(),
      api.currentUser()
    ])
    for (const [key] of fields) goals[key] = saved[key] ?? ''
    accentColor.value = theme.accent_color
    currentUser.value = user
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function save() {
  error.value = ''
  const payload = Object.fromEntries(
    fields.map(([key]) => [key, goals[key] === '' ? null : Number(goals[key])])
  )
  saving.value = true
  try {
    const [saved, theme] = await Promise.all([
      api.updateProfileGoals(payload),
      api.updateProfileTheme({ accent_color: accentColor.value })
    ])
    for (const [key] of fields) goals[key] = saved[key] ?? ''
    accentColor.value = theme.accent_color
    applyAccentColor(theme.accent_color)
    notify('Profile saved')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <header class="page-head">
    <h1>Profile</h1>
    <p class="muted">Set daily targets to track your progress on Today.</p>
    <p v-if="currentUser?.name" class="muted">
      Signed in as <strong>{{ currentUser.name }}</strong> · {{ currentUser.email }}
    </p>
  </header>

  <form class="card profile-form" @submit.prevent="save" :aria-busy="loading || saving">
    <p v-if="loading" class="muted">Loading profile…</p>

    <div v-else class="grid2">
      <div v-for="[key, label, unit] in fields" :key="key" class="field">
        <label :for="`goal-${key}`">{{ label }} goal</label>
        <div class="input-unit">
          <input
            :id="`goal-${key}`"
            v-model="goals[key]"
            class="unit-input"
            type="number"
            inputmode="decimal"
            min="0"
            step="any"
            :placeholder="`No ${label.toLowerCase()} goal`"
          />
          <span aria-hidden="true">{{ unit }}</span>
        </div>
      </div>
    </div>

    <fieldset v-if="!loading" class="accent-picker">
      <legend>Accent colour</legend>
      <div class="accent-options">
        <label v-for="[value, label] in ACCENT_COLORS" :key="value" class="accent-option">
          <input v-model="accentColor" type="radio" name="accent-color" :value="value" />
          <span class="accent-swatch" :class="`swatch-${value}`" aria-hidden="true"></span>
          <span>{{ label }}</span>
        </label>
      </div>
    </fieldset>

    <p class="muted hint">Leave a field empty to hide that target from Today.</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <button type="submit" class="btn" :disabled="loading || saving">
      {{ saving ? 'Saving…' : 'Save goals' }}
    </button>
  </form>
</template>
