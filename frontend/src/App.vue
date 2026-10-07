<script setup>
import { onMounted, ref } from 'vue'
import TodayView from './components/TodayView.vue'
import FoodsView from './components/FoodsView.vue'
import IngredientsView from './components/IngredientsView.vue'
import ProfileView from './components/ProfileView.vue'
import LeaderboardView from './components/LeaderboardView.vue'
import FoodDialog from './components/FoodDialog.vue'
import IngredientDialog from './components/IngredientDialog.vue'
import { api } from './api'
import { loadFoods, loadIngredients, store } from './foods'
import { loadAccentColor } from './theme'
import {
  notify,
  registerFoodDialog,
  registerIngredientDialog,
  ui
} from './ui'

const tab = ref('today')
const foodDialogEl = ref(null)
const ingredientDialogEl = ref(null)
const nameDialogEl = ref(null)
const name = ref('')
const nameSaving = ref(false)
const nameError = ref('')

onMounted(async () => {
  registerFoodDialog(foodDialogEl.value)
  registerIngredientDialog(ingredientDialogEl.value)
  try {
    const user = await api.currentUser()
    store.userId = user.id
    if (!user.name) nameDialogEl.value?.showModal()
    await Promise.all([loadFoods(), loadIngredients(), loadAccentColor()])
  } catch (e) {
    notify(e.message, 'error')
  }
})

async function saveName() {
  nameError.value = ''
  const trimmedName = name.value.trim()
  if (!trimmedName) {
    nameError.value = 'Enter a name to continue.'
    return
  }

  nameSaving.value = true
  try {
    await api.updateCurrentUser({ name: trimmedName })
    nameDialogEl.value?.close()
  } catch (e) {
    nameError.value = e.message
  } finally {
    nameSaving.value = false
  }
}
</script>

<template>
  <a class="skip-link" href="#main">Skip to content</a>

  <main id="main" class="page">
    <TodayView v-if="tab === 'today'" />
    <FoodsView v-else-if="tab === 'foods'" />
    <IngredientsView v-else-if="tab === 'ingredients'" />
    <LeaderboardView v-else-if="tab === 'leaderboard'" />
    <ProfileView v-else-if="tab === 'profile'" />
  </main>

  <nav class="tabbar" aria-label="Main">
    <div class="tabbar-inner">
      <button type="button" :aria-current="tab === 'today' ? 'page' : undefined" @click="tab = 'today'">
        <span aria-hidden="true">🍽️</span>
        Today
      </button>
      <button type="button" :aria-current="tab === 'foods' ? 'page' : undefined" @click="tab = 'foods'">
        <span aria-hidden="true">🥑</span>
        Foods
      </button>
      <button
        type="button"
        :aria-current="tab === 'ingredients' ? 'page' : undefined"
        @click="tab = 'ingredients'"
      >
        <span aria-hidden="true">🥕</span>
        Ingredients
      </button>
      <button type="button" :aria-current="tab === 'profile' ? 'page' : undefined" @click="tab = 'profile'">
        <span aria-hidden="true">👤</span>
        Profile
      </button>
      <button type="button" :aria-current="tab === 'leaderboard' ? 'page' : undefined" @click="tab = 'leaderboard'">
        <span aria-hidden="true">🏆</span>
        Top 3
      </button>
    </div>
  </nav>

  <FoodDialog ref="foodDialogEl" />
  <IngredientDialog ref="ingredientDialogEl" />

  <dialog
    ref="nameDialogEl"
    class="sheet"
    aria-labelledby="name-dialog-title"
    @cancel.prevent
  >
    <form class="sheet-body" @submit.prevent="saveName">
      <header class="sheet-head">
        <h2 id="name-dialog-title">What should we call you?</h2>
      </header>
      <div class="sheet-scroll">
        <div class="field">
          <label for="profile-name">Your name</label>
          <input
            id="profile-name"
            v-model="name"
            type="text"
            maxlength="100"
            autocomplete="name"
            autofocus
            required
          />
        </div>
        <p v-if="nameError" class="error" role="alert">{{ nameError }}</p>
      </div>
      <footer class="sheet-foot">
        <button type="submit" class="btn" :disabled="nameSaving">
          {{ nameSaving ? 'Saving…' : 'Continue' }}
        </button>
      </footer>
    </form>
  </dialog>

  <div class="toast-region" role="status" aria-live="polite">
    <p v-if="ui.toast" class="toast" :class="ui.toast.kind">{{ ui.toast.message }}</p>
  </div>
</template>
