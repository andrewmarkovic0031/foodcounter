<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { store } from '../foods'
import { formatDay, formatTime, shiftDay, toDay } from '../dates'
import { formatCalories } from '../nutrition'
import { notify } from '../ui'
import MealDialog from './MealDialog.vue'

const day = ref(toDay())
const meals = ref([])
const yesterdayMeals = ref([])
const showYesterdayMeals = ref(true)
const summary = ref(null)
const goals = ref(null)
const loading = ref(false)
const repeatingMealId = ref(null)
const mealDialog = ref(null)
let token = 0 // ignore responses from a day the user has already navigated away from

async function load() {
  const mine = ++token
  loading.value = true
  try {
    const selectedDay = day.value
    const [list, totals, previousDayMeals] = await Promise.all([
      api.listMeals(selectedDay),
      api.dailySummary(selectedDay),
      selectedDay === toDay() && showYesterdayMeals.value
        ? api.listMeals(shiftDay(selectedDay, -1))
        : []
    ])
    if (mine !== token) return
    meals.value = [...list].sort((a, b) => a.eaten_at.localeCompare(b.eaten_at))
    yesterdayMeals.value = previousDayMeals
    summary.value = totals
  } catch (e) {
    if (mine === token) notify(e.message, 'error')
  } finally {
    if (mine === token) loading.value = false
  }
}

watch(day, load)
watch(() => store.revision, load) // a food was edited/deleted: refresh embedded food data

onMounted(async () => {
  try {
    const user = await api.currentUser()
    showYesterdayMeals.value = user.show_yesterday_meals
  } catch (e) {
    notify(e.message, 'error')
  }
  await load()
})

api.profileGoals()
  .then((value) => {
    goals.value = value
  })
  .catch((e) => notify(e.message, 'error'))

const isToday = computed(() => day.value === toDay())
const longDay = computed(() => formatDay(day.value))
const dayLabel = computed(() => {
  const today = toDay()
  if (day.value === today) return 'Today'
  if (day.value === shiftDay(today, -1)) return 'Yesterday'
  if (day.value === shiftDay(today, 1)) return 'Tomorrow'
  return longDay.value
})

function setDay(value) {
  if (value) day.value = value // ignore the empty value a cleared date input gives
}

function onSaved(savedDay) {
  // Jump to the day the meal was saved on so it never "disappears" from view.
  if (savedDay && savedDay !== day.value) day.value = savedDay
  else load()
}

async function repeatMeal(meal) {
  if (repeatingMealId.value !== null) return
  repeatingMealId.value = meal.id
  try {
    await api.createMeal({
      meal_type: meal.meal_type,
      items: meal.items.map((item) => ({
        food_id: item.food.id,
        quantity: item.quantity
      }))
    })
    await load()
    notify('Meal repeated for today')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    repeatingMealId.value = null
  }
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
const qty = (n) => String(Math.round(n * 100) / 100)
const round = (n) => Math.round(n ?? 0)
const goalMetrics = [
  ['kilojoules', 'Kilojoules', 'kJ'],
  ['protein', 'Protein', 'g'],
  ['carbohydrates', 'Carbohydrates', 'g'],
  ['fat', 'Fat', 'g'],
  ['sugar', 'Sugar', 'g']
]
const progressPercent = (key) => {
  const target = goals.value?.[key]
  if (target == null || target === 0) return 0
  return Math.round(((summary.value?.[key] ?? 0) / target) * 100)
}
const isOverGoal = (key) =>
  key !== 'protein' &&
  goals.value?.[key] != null &&
  (summary.value?.[key] ?? 0) > goals.value[key]
const goalProgressLabel = (key) => {
  if (goals.value?.[key] === 0) {
    return (summary.value?.[key] ?? 0) > 0 ? 'Over goal' : '0%'
  }
  const percent = progressPercent(key)
  return isOverGoal(key) ? `${percent}% · over goal` : `${percent}%`
}
const formatMetric = (value) => Math.round((value ?? 0) * 10) / 10
</script>

<template>
  <header class="page-head">
    <h1>{{ dayLabel }}</h1>
    <p v-if="dayLabel !== longDay" class="muted">{{ longDay }}</p>
  </header>

  <div class="daynav">
    <button type="button" class="icon-btn" aria-label="Previous day" @click="day = shiftDay(day, -1)">‹</button>
    <input type="date" aria-label="Choose date" :value="day" @change="setDay($event.target.value)" />
    <button type="button" class="icon-btn" aria-label="Next day" @click="day = shiftDay(day, 1)">›</button>
  </div>
  <button v-if="!isToday" type="button" class="btn ghost back-today" @click="day = toDay()">Back to today</button>

  <section class="card summary" aria-labelledby="totals-heading" :aria-busy="loading">
    <h2 id="totals-heading" class="sr-only">Daily totals</h2>
    <div class="kilojoules">
      <span class="kilojoules-num">{{ round(summary?.kilojoules) }}</span>
      <span class="muted">Kilojoules</span>
      <span class="muted">{{ formatCalories(summary?.kilojoules) }}</span>
    </div>
    <dl class="macros">
      <div>
        <dt>Protein</dt>
        <dd>{{ round(summary?.protein) }} g</dd>
      </div>
      <div>
        <dt>Carbohydrates</dt>
        <dd>{{ round(summary?.carbohydrates) }} g</dd>
      </div>
      <div>
        <dt>Fat</dt>
        <dd>{{ round(summary?.fat) }} g</dd>
      </div>
      <div>
        <dt>Sugar</dt>
        <dd>{{ round(summary?.sugar) }} g</dd>
      </div>
    </dl>
    <div v-if="goalMetrics.some(([key]) => goals?.[key] != null)" class="goal-progress">
      <h2>Daily goal progress</h2>
      <div
        v-for="[key, label, unit] in goalMetrics.filter(([key]) => goals?.[key] != null)"
        :key="key"
        :class="{ 'goal-over': isOverGoal(key) }"
      >
        <div class="goal-progress-label">
          <span>{{ label }}</span>
          <span>
            <template v-if="key === 'kilojoules'">
              {{ formatMetric(summary?.[key]) }} kJ ({{ formatCalories(summary?.[key]) }})
              / {{ formatMetric(goals[key]) }} kJ ({{ formatCalories(goals[key]) }})
            </template>
            <template v-else>{{ formatMetric(summary?.[key]) }} / {{ formatMetric(goals[key]) }} {{ unit }}</template>
            · {{ goalProgressLabel(key) }}
          </span>
        </div>
        <progress
          :value="Math.min(progressPercent(key), 100)"
          max="100"
          :aria-label="`${label}: ${formatMetric(summary?.[key])} of ${formatMetric(goals[key])} ${unit}${key === 'kilojoules' ? ` (${formatCalories(summary?.[key])} of ${formatCalories(goals[key])})` : ''}${isOverGoal(key) ? ', over goal' : ''}`"
        />
      </div>
    </div>
  </section>

  <section aria-labelledby="meals-heading" :aria-busy="loading">
    <h2 id="meals-heading" class="sr-only">Meals</h2>
    <p v-if="loading && !meals.length" class="muted">Loading…</p>
    <p v-else-if="!meals.length" class="card empty">No meals logged for this day yet.</p>
    <ul v-else class="meal-list">
      <li v-for="m in meals" :key="m.id" class="card meal">
        <div class="meal-head">
          <h3 class="meal-title">
            {{ cap(m.meal_type) }}
            <span class="muted">· {{ formatTime(m.eaten_at) }}</span>
          </h3>
          <strong>{{ round(m.total_kilojoules) }} kJ ({{ formatCalories(m.total_kilojoules) }})</strong>
        </div>
        <ul v-if="m.items.length" class="items">
          <li v-for="i in m.items" :key="i.id">{{ qty(i.quantity) }} × {{ i.food.name }}</li>
        </ul>
        <p v-if="m.notes" class="muted notes">{{ m.notes }}</p>
        <button
          type="button"
          class="btn ghost"
          :aria-label="`Edit ${m.meal_type} at ${formatTime(m.eaten_at)}`"
          @click="mealDialog.open(m)"
        >
          Edit
        </button>
      </li>
    </ul>
  </section>
<section
    v-if="isToday && showYesterdayMeals && yesterdayMeals.length"
    aria-labelledby="repeat-meals-heading"
  >
    <h2 id="repeat-meals-heading">Yesterday’s meals</h2>
    <p class="muted">Repeat a meal to add it to today.</p>
    <ul class="meal-list">
      <li v-for="m in yesterdayMeals" :key="m.id" class="card meal">
        <div class="meal-head">
          <h3 class="meal-title">
            {{ cap(m.meal_type) }}
            <span class="muted">· {{ formatTime(m.eaten_at) }}</span>
          </h3>
          <button
            type="button"
            class="btn secondary"
            :disabled="repeatingMealId !== null"
            :aria-label="`Repeat ${m.meal_type} from yesterday`"
            @click="repeatMeal(m)"
          >
            {{ repeatingMealId === m.id ? 'Adding…' : 'Repeat' }}
          </button>
        </div>
        <ul v-if="m.items.length" class="items">
          <li v-for="i in m.items" :key="i.id">{{ qty(i.quantity) }} × {{ i.food.name }}</li>
        </ul>
      </li>
    </ul>
  </section>
  <button type="button" class="btn fab" @click="mealDialog.open()">+ Log meal</button>

  <MealDialog ref="mealDialog" :day="day" @saved="onSaved" />
</template>
