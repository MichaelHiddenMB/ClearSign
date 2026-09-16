import { useCallback, useEffect, useState } from 'react'
import { loadSettings, saveSettings, themeById, type Settings } from '../lib/settings'

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(loadSettings)

  useEffect(() => {
    saveSettings(settings)
  }, [settings])

  // The app chrome follows the reading surface so a dark reader is not framed by a bright shell.
  useEffect(() => {
    const theme = themeById(settings.themeId)
    document.documentElement.dataset.chrome = theme.chrome
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (meta) meta.content = theme.chrome === 'dark' ? '#0e1114' : '#ffffff'
  }, [settings.themeId])

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...patch }))
  }, [])

  return { settings, update }
}
