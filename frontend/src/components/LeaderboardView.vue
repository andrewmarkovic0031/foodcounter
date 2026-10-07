<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { formatEnergy } from '../nutrition'

const leaderboard = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    leaderboard.value = await api.kilojouleLeaderboard()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

</script>

<template>
  <header class="page-head">
    <h1>Leaderboard</h1>
    <p class="muted">Top 3 by kilojoules logged all time.</p>
  </header>

  <section class="card leaderboard" aria-label="All-time kilojoule leaderboard">
    <p v-if="loading" class="muted">Loading leaderboard…</p>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="!leaderboard.length" class="muted empty">
      No meals have been logged yet.
    </p>
    <ol v-else class="leaderboard-list">
      <li v-for="(entry, index) in leaderboard" :key="entry.user_id">
        <span class="leaderboard-rank" :aria-label="`Place ${index + 1}`">{{ index + 1 }}</span>
        <strong class="leaderboard-name">{{ entry.name }}</strong>
        <span class="leaderboard-score">{{ formatEnergy(entry.kilojoules) }}</span>
      </li>
    </ol>
  </section>
</template>
