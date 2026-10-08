<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { foodsChanged, loadFoods, loadIngredients } from '../foods'
import { ACCENT_COLORS, applyAccentColor } from '../theme'
import { notify } from '../ui'
import { formatCalories } from '../nutrition'

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
const libraryPreferences = reactive({
  share_foods: false,
  share_ingredients: false,
  see_shared_foods: false,
  see_shared_ingredients: false,
  show_yesterday_meals: true
})

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
    for (const key of Object.keys(libraryPreferences)) {
      libraryPreferences[key] = user[key]
    }
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
    const [saved, theme, user] = await Promise.all([
      api.updateProfileGoals(payload),
      api.updateProfileTheme({ accent_color: accentColor.value }),
      api.updateLibraryPreferences(libraryPreferences)
    ])
    for (const [key] of fields) goals[key] = saved[key] ?? ''
    accentColor.value = theme.accent_color
    currentUser.value = user
    applyAccentColor(theme.accent_color)
    await Promise.all([loadFoods(), loadIngredients()])
    foodsChanged()
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
        <span v-if="key === 'kilojoules' && goals[key] !== ''" class="muted hint">
          {{ formatCalories(Number(goals[key])) }}
        </span>
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

    <fieldset v-if="!loading" class="library-preferences">
      <legend>Library sharing</legend>
      <label class="library-preference">
        <input v-model="libraryPreferences.share_foods" type="checkbox" />
        <span>Share my foods publicly</span>
      </label>
      <label class="library-preference">
        <input v-model="libraryPreferences.share_ingredients" type="checkbox" />
        <span>Share my ingredients publicly</span>
      </label>
      <label class="library-preference">
        <input v-model="libraryPreferences.see_shared_foods" type="checkbox" />
        <span>Show foods other people share</span>
      </label>
      <label class="library-preference">
        <input v-model="libraryPreferences.see_shared_ingredients" type="checkbox" />
        <span>Show ingredients other people share</span>
      </label>
      <p class="muted hint">
        Changes take effect when you save your profile. Shared foods include their recipe ingredients.
        Sharing is limited to people who can already access this app.
      </p>
    </fieldset>

    <fieldset v-if="!loading" class="library-preferences">
      <legend>Today screen</legend>
      <label class="library-preference">
        <input v-model="libraryPreferences.show_yesterday_meals" type="checkbox" />
        <span>Show yesterday’s meals to repeat on Today</span>
      </label>
      <p class="muted hint">Changes take effect when you save your profile.</p>
    </fieldset>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <button type="submit" class="btn" :disabled="loading || saving">
      {{ saving ? 'Saving…' : 'Save profile' }}
    </button>
  </form>
</template>
