// Date helpers. The API stores naive *local* times, so everything here stays in
// local time. Never use toISOString(): it converts to UTC and shifts the day.

export const pad = (n) => String(n).padStart(2, '0')

// Local calendar day as YYYY-MM-DD
export function toDay(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function fromDay(day) {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function shiftDay(day, delta) {
  const d = fromDay(day)
  d.setDate(d.getDate() + delta)
  return toDay(d)
}

export function formatDay(day) {
  return fromDay(day).toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}

// "YYYY-MM-DDTHH:mm", the format <input type="datetime-local"> uses
export function toLocalInput(d) {
  return `${toDay(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// API values look like "2026-10-04T08:30:00.123456" (no timezone). Parse as local,
// dropping the microseconds that some browsers (Safari) are picky about.
export function parseLocal(s) {
  return new Date(s.replace(/\.\d+$/, ''))
}

export function formatTime(s) {
  return parseLocal(s).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}
