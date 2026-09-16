import { useCallback, useEffect, useState } from 'react'
import { interfaceStyleVars, loadSettings, readerStyleVars, saveSettings, themeById, type Settings } from '../lib/settings'

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(loadSettings)

  useEffect(() => {
    saveSettings(settings)
  }, [settings])

  // The whole interface follows the reading settings: colours, typeface, spacing and scale.
  useEffect(() => {
    const root = document.documentElement
    const theme = themeById(settings.themeId)
    root.dataset.chrome = theme.chrome
    for (const [name, value] of Object.entries({ ...readerStyleVars(settings), ...interfaceStyleVars(settings) })) {
      root.style.setProperty(name, String(value))
    }
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (meta) meta.content = theme.bg
  }, [settings])

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...patch }))
  }, [])

  return { settings, update }
}
