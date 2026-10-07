const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })

export function formatEnergy(kilojoules) {
  if (kilojoules == null) return '– kJ (– kcal)'
  const calories = kilojoules / 4.184
  return `${numberFormat.format(kilojoules)} kJ (${numberFormat.format(calories)} kcal)`
}

export function formatCalories(kilojoules) {
  if (kilojoules == null) return '– kcal'
  return `${numberFormat.format(kilojoules / 4.184)} kcal`
}
