import { reactive } from 'vue'

// --- toast messages (rendered in App.vue inside a polite live region) ---
export const ui = reactive({ toast: null })
let timer

export function notify(message, kind = 'info') {
  ui.toast = { message, kind }
  clearTimeout(timer)
  timer = setTimeout(() => {
    ui.toast = null
  }, 6000)
}

// --- the food dialog lives in App.vue so any screen can open it ---
let foodDialog = null
let ingredientDialog = null

export function registerFoodDialog(instance) {
  foodDialog = instance
}

export function openFoodDialog(food = null, onSaved = null) {
  foodDialog?.open(food, onSaved)
}

export function registerIngredientDialog(instance) {
  ingredientDialog = instance
}

export function openIngredientDialog(ingredient = null) {
  ingredientDialog?.open(ingredient)
}
