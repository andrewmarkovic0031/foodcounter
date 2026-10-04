import { api } from './api'

export const ACCENT_COLORS = [
  ['violet', 'Violet'],
  ['blue', 'Blue'],
  ['teal', 'Teal'],
  ['amber', 'Amber'],
  ['rose', 'Rose']
]

export function applyAccentColor(color) {
  document.documentElement.dataset.accent = color
}

export async function loadAccentColor() {
  const theme = await api.profileTheme()
  applyAccentColor(theme.accent_color)
  return theme.accent_color
}
