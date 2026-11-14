import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

export const isThemeMode = (value: unknown): value is ThemeMode =>
  value === 'light' || value === 'dark' || value === 'system'

const readTheme = (): ThemeMode => {
  try {
    const saved = localStorage.getItem('theme')
    if (isThemeMode(saved)) return saved
  } catch {
    // The desktop config remains authoritative if browser storage is unavailable.
  }
  return 'system'
}

const systemTheme = window.matchMedia('(prefers-color-scheme: dark)')
export const themeMode = ref<ThemeMode>(readTheme())

const applyTheme = () => {
  const dark = themeMode.value === 'dark' || (themeMode.value === 'system' && systemTheme.matches)
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

export const setTheme = (mode: ThemeMode) => {
  themeMode.value = mode
  applyTheme()
  try {
    localStorage.setItem('theme', mode)
  } catch {
    // Saving gui_config.json does not depend on localStorage.
  }
}

// Apply before mounting so cached preferences also cover the initial render.
applyTheme()
systemTheme.addEventListener('change', applyTheme)
