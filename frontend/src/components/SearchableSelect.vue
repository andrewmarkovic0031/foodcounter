<script setup>
import { computed, ref, useId } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true },
  label: { type: String, required: true },
  placeholder: { type: String, default: 'Search…' }
})

const emit = defineEmits(['update:modelValue'])

const id = useId()
const query = ref('')
const open = ref(false)
const activeIndex = ref(-1)

const selected = computed(() =>
  props.options.find((option) => String(option.id) === String(props.modelValue))
)
const visibleLabel = computed(() => selected.value?.label ?? selected.value?.name ?? '')
const filteredOptions = computed(() => {
  const search = query.value.trim().toLocaleLowerCase()
  return search
    ? props.options.filter((option) =>
        (option.label ?? option.name).toLocaleLowerCase().includes(search)
      )
    : props.options
})

function showOptions() {
  if (!open.value) {
    query.value = ''
    activeIndex.value = -1
  }
  open.value = true
}

function choose(option) {
  emit('update:modelValue', option.id)
  query.value = ''
  open.value = false
  activeIndex.value = -1
}

function onKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    showOptions()
    activeIndex.value = Math.min(activeIndex.value + 1, filteredOptions.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    showOptions()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (event.key === 'Enter' && open.value) {
    event.preventDefault()
    const option = filteredOptions.value[activeIndex.value < 0 ? 0 : activeIndex.value]
    if (option) choose(option)
  } else if (event.key === 'Escape' && open.value) {
    event.preventDefault()
    open.value = false
    query.value = ''
    activeIndex.value = -1
  }
}
</script>

<template>
  <div class="search-select">
    <input
      :id="id"
      :value="open ? query : visibleLabel"
      type="text"
      role="combobox"
      aria-autocomplete="list"
      aria-haspopup="listbox"
      :aria-label="label"
      :aria-expanded="open"
      :aria-controls="`${id}-options`"
      :aria-activedescendant="activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined"
      :placeholder="placeholder"
      autocomplete="off"
      @focus="showOptions"
      @click="showOptions"
      @input="query = $event.target.value; activeIndex = -1; open = true"
      @keydown="onKeydown"
      @blur="open = false; query = ''; activeIndex = -1"
    />
    <div v-if="open" :id="`${id}-options`" class="search-select-options" role="listbox" :aria-label="label">
      <p v-if="!filteredOptions.length" class="search-select-empty">No matches</p>
      <button
        v-for="(option, index) in filteredOptions"
        :id="`${id}-option-${index}`"
        :key="option.id"
        type="button"
        role="option"
        class="search-select-option"
        :aria-selected="String(option.id) === String(modelValue)"
        :class="{ active: index === activeIndex }"
        @mousedown.prevent
        @click="choose(option)"
      >
        {{ option.label ?? option.name }}
      </button>
    </div>
  </div>
</template>
