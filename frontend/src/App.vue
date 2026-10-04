<script setup>
import { onMounted, ref } from 'vue'
import TodayView from './components/TodayView.vue'
import FoodsView from './components/FoodsView.vue'
import IngredientsView from './components/IngredientsView.vue'
import ProfileView from './components/ProfileView.vue'
import FoodDialog from './components/FoodDialog.vue'
import IngredientDialog from './components/IngredientDialog.vue'
import { loadFoods, loadIngredients } from './foods'
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

onMounted(() => {
  registerFoodDialog(foodDialogEl.value)
  registerIngredientDialog(ingredientDialogEl.value)
  Promise.all([loadFoods(), loadIngredients(), loadAccentColor()]).catch((e) =>
    notify(e.message, 'error')
  )
})
</script>

<template>
  <a class="skip-link" href="#main">Skip to content</a>

  <main id="main" class="page">
    <TodayView v-if="tab === 'today'" />
    <FoodsView v-else-if="tab === 'foods'" />
    <IngredientsView v-else-if="tab === 'ingredients'" />
    <ProfileView v-else />
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
    </div>
  </nav>

  <FoodDialog ref="foodDialogEl" />
  <IngredientDialog ref="ingredientDialogEl" />

  <div class="toast-region" role="status" aria-live="polite">
    <p v-if="ui.toast" class="toast" :class="ui.toast.kind">{{ ui.toast.message }}</p>
  </div>
</template>
