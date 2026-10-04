<script setup>
import { computed, ref } from 'vue'
import { store } from '../foods'
import { openFoodDialog } from '../ui'

const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return q ? store.foods.filter((f) => f.name.toLowerCase().includes(q)) : store.foods
})

const grams = (v) => (v == null ? '–' : `${Math.round(v * 10) / 10}`)
</script>

<template>
  <header class="page-head">
    <h1>Foods</h1>
    <p class="muted">Foods are recipes made from ingredients. Nutrition is calculated per serving.</p>
  </header>

  <div class="field">
    <label for="food-search" class="sr-only">Search foods</label>
    <input id="food-search" v-model="query" type="search" placeholder="Search foods" autocomplete="off" />
  </div>

  <section aria-label="Food list">
    <p v-if="!store.loaded" class="muted">Loading…</p>
    <p v-else-if="!store.foods.length" class="card empty">No foods yet. Tap “New food” to add your first.</p>
    <p v-else-if="!filtered.length" class="card empty">No foods match “{{ query }}”.</p>
    <ul v-else class="food-list">
      <li v-for="f in filtered" :key="f.id">
        <button type="button" class="card food" @click="openFoodDialog(f)">
          <span class="food-name"><span class="sr-only">Edit </span>{{ f.name }}</span>
          <span class="muted">
            {{ f.ingredients.length }} ingredients · {{ f.servings }} recipe servings ·
            {{ f.kilojoules != null ? `${Math.round(f.kilojoules)} kilojoules` : 'No kilojoules' }}
            · P {{ grams(f.protein) }} · C {{ grams(f.carbohydrates) }} · F {{ grams(f.fat) }} · S {{ grams(f.sugar) }}
          </span>
        </button>
      </li>
    </ul>
  </section>

  <button type="button" class="btn fab" @click="openFoodDialog()">+ New food</button>
</template>
