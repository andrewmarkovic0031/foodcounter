// Thin wrapper around fetch for the FastAPI backend (same origin, under /api).

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`/api${path}`, {
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      ...options,
    })
  } catch {
    throw new Error('Cannot reach the server. Check your connection and try again.')
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') message = data.detail
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join(', ')
    } catch {
      /* keep the generic message */
    }
    throw new Error(message)
  }
  return res.status === 204 ? null : res.json()
}

const withBody = (method, body) => ({ method, body: JSON.stringify(body) })

export const api = {
  // ingredients
  listIngredients: () => request('/ingredients?limit=200'),
  searchUSDAIngredients: (query) =>
    request(`/ingredients/usda/search?q=${encodeURIComponent(query)}&limit=10`),
  createIngredient: (body) => request('/ingredients', withBody('POST', body)),
  updateIngredient: (id, body) => request(`/ingredients/${id}`, withBody('PATCH', body)),
  deleteIngredient: (id) => request(`/ingredients/${id}`, { method: 'DELETE' }),

  // foods (the API caps a page at 200; plenty for a personal food list)
  listFoods: () => request('/foods?limit=200'),
  createFood: (body) => request('/foods', withBody('POST', body)),
  updateFood: (id, body) => request(`/foods/${id}`, withBody('PATCH', body)),
  deleteFood: (id) => request(`/foods/${id}`, { method: 'DELETE' }),

  // meals
  listMeals: (day) => request(`/meals?day=${day}&limit=200`),
  createMeal: (body) => request('/meals', withBody('POST', body)),
  updateMeal: (id, body) => request(`/meals/${id}`, withBody('PATCH', body)),
  deleteMeal: (id) => request(`/meals/${id}`, { method: 'DELETE' }),

  // summary
  dailySummary: (day) => request(`/summary/daily?day=${day}`),

  // profile
  profileGoals: () => request('/profile/goals'),
  updateProfileGoals: (body) => request('/profile/goals', withBody('PUT', body)),
  profileTheme: () => request('/profile/theme'),
  updateProfileTheme: (body) => request('/profile/theme', withBody('PUT', body)),
}
