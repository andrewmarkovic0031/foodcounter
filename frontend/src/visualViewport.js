export function trackVisualViewport(element) {
  const viewport = window.visualViewport

  function update() {
    const height = viewport?.height ?? window.innerHeight
    const offsetTop = viewport?.offsetTop ?? 0
    element.style.setProperty('--sheet-viewport-height', `${height}px`)
    element.style.setProperty('--sheet-viewport-top', `${offsetTop}px`)
  }

  update()
  viewport?.addEventListener('resize', update)
  viewport?.addEventListener('scroll', update)
  window.addEventListener('resize', update)

  return () => {
    viewport?.removeEventListener('resize', update)
    viewport?.removeEventListener('scroll', update)
    window.removeEventListener('resize', update)
    element.style.removeProperty('--sheet-viewport-height')
    element.style.removeProperty('--sheet-viewport-top')
  }
}
