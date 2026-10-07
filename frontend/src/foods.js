import { reactive } from 'vue'
import { api } from './api'

// Shared catalog, used by the Foods and Ingredients tabs and the meal form.
export const store = reactive({
  foods: [],
  ingredients: [],
  userId: null,
  loaded: false,
  ingredientsLoaded: false,
  revision: 0
})

export async function loadFoods() {
  store.foods = await api.listFoods()
  store.loaded = true
}

export async function loadIngredients() {
  store.ingredients = await api.listIngredients()
  store.ingredientsLoaded = true
}

// Call after a food is edited or deleted so meal lists re-fetch their embedded food data.
export function foodsChanged() {
  store.revision++
}
