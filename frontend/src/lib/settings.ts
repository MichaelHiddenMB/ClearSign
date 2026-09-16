export type ThemeId =
  | 'black-on-white'
  | 'white-on-black'
  | 'yellow-on-black'
  | 'black-on-yellow'
  | 'navy-on-ivory'
  | 'white-on-navy'

export interface ReaderTheme {
  id: ThemeId
  label: string
  fg: string
  bg: string
  /** Background used to mark the word currently being read aloud. */
  mark: string
  /** Which app chrome palette suits this reading surface. */
  chrome: 'light' | 'dark'
}

export const THEMES: ReaderTheme[] = [
  { id: 'black-on-white', label: 'Black on white', fg: '#000000', bg: '#FFFFFF', mark: '#FFE45C', chrome: 'light' },
  { id: 'white-on-black', label: 'White on black', fg: '#FFFFFF', bg: '#000000', mark: '#4F4A00', chrome: 'dark' },
  { id: 'yellow-on-black', label: 'Yellow on black', fg: '#FFE45C', bg: '#000000', mark: '#3F3A1A', chrome: 'dark' },
  { id: 'black-on-yellow', label: 'Black on yellow', fg: '#000000', bg: '#FFE45C', mark: '#FFFFFF', chrome: 'light' },
  { id: 'navy-on-ivory', label: 'Navy on ivory', fg: '#14213D', bg: '#FAF6EA', mark: '#F2D66B', chrome: 'light' },
  { id: 'white-on-navy', label: 'White on navy', fg: '#FFFFFF', bg: '#14213D', mark: '#2F4A85', chrome: 'dark' },
]

export type FontId = 'hyperlegible' | 'lexend' | 'system' | 'serif'

export interface ReaderFont {
  id: FontId
  label: string
  stack: string
}

export const FONTS: ReaderFont[] = [
  { id: 'hyperlegible', label: 'Atkinson Hyperlegible', stack: '"Atkinson Hyperlegible", system-ui, sans-serif' },
  { id: 'lexend', label: 'Lexend', stack: 'Lexend, system-ui, sans-serif' },
  { id: 'system', label: 'System sans-serif', stack: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' },
  { id: 'serif', label: 'Serif', stack: 'Georgia, "Times New Roman", serif' },
]

export type LineSpacing = 'compact' | 'normal' | 'loose'

export const LINE_SPACING: Record<LineSpacing, number> = {
  compact: 1.15,
  normal: 1.4,
  loose: 1.8,
}

export interface Settings {
  /** Reader text size in CSS pixels. */
  fontSize: number
  fontId: FontId
  themeId: ThemeId
  lineSpacing: LineSpacing
  bold: boolean
  /** Extra tracking in em. */
  letterSpacing: number
  /** Web Speech API rate, 0.5–1.5. */
  speechRate: number
  /** SpeechSynthesisVoice.voiceURI, or empty for the browser default. */
  voiceURI: string
}

export const FONT_SIZE_MIN = 24
export const FONT_SIZE_MAX = 160
export const FONT_SIZE_STEP = 8

export const DEFAULT_SETTINGS: Settings = {
  fontSize: 48,
  fontId: 'hyperlegible',
  themeId: 'black-on-white',
  lineSpacing: 'normal',
  bold: false,
  letterSpacing: 0,
  speechRate: 1,
  voiceURI: '',
}

const STORAGE_KEY = 'clearsign.settings.v1'

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SETTINGS
    const parsed = JSON.parse(raw) as Partial<Settings>
    return sanitize({ ...DEFAULT_SETTINGS, ...parsed })
  } catch {
    return DEFAULT_SETTINGS
  }
}

export function saveSettings(settings: Settings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // Storage can be unavailable (private mode, quota). Settings still apply for the session.
  }
}

function sanitize(s: Settings): Settings {
  return {
    ...s,
    fontSize: clamp(Math.round(s.fontSize), FONT_SIZE_MIN, FONT_SIZE_MAX),
    fontId: FONTS.some((f) => f.id === s.fontId) ? s.fontId : DEFAULT_SETTINGS.fontId,
    themeId: THEMES.some((t) => t.id === s.themeId) ? s.themeId : DEFAULT_SETTINGS.themeId,
    lineSpacing: s.lineSpacing in LINE_SPACING ? s.lineSpacing : DEFAULT_SETTINGS.lineSpacing,
    letterSpacing: clamp(s.letterSpacing, 0, 0.2),
    speechRate: clamp(s.speechRate, 0.5, 1.5),
  }
}

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Number.isFinite(n) ? n : min))
}

export function themeById(id: ThemeId): ReaderTheme {
  return THEMES.find((t) => t.id === id) ?? THEMES[0]
}

export function fontById(id: FontId): ReaderFont {
  return FONTS.find((f) => f.id === id) ?? FONTS[0]
}
