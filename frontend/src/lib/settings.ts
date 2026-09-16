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
  /** Colour for primary actions, the wordmark and focus rings on this surface. */
  accent: string
  /** Text colour on top of the accent. */
  accentInk: string
  /** Whether native controls should render light or dark. */
  chrome: 'light' | 'dark'
}

export const THEMES: ReaderTheme[] = [
  { id: 'black-on-white', label: 'Black on white', fg: '#000000', bg: '#FFFFFF', mark: '#FFE45C', accent: '#1A47B8', accentInk: '#FFFFFF', chrome: 'light' },
  { id: 'white-on-black', label: 'White on black', fg: '#FFFFFF', bg: '#000000', mark: '#4F4A00', accent: '#FFFFFF', accentInk: '#000000', chrome: 'dark' },
  { id: 'yellow-on-black', label: 'Yellow on black', fg: '#FFE45C', bg: '#000000', mark: '#3F3A1A', accent: '#FFE45C', accentInk: '#000000', chrome: 'dark' },
  { id: 'black-on-yellow', label: 'Black on yellow', fg: '#000000', bg: '#FFE45C', mark: '#FFFFFF', accent: '#000000', accentInk: '#FFE45C', chrome: 'light' },
  { id: 'navy-on-ivory', label: 'Navy on ivory', fg: '#14213D', bg: '#FAF6EA', mark: '#F2D66B', accent: '#14213D', accentInk: '#FAF6EA', chrome: 'light' },
  { id: 'white-on-navy', label: 'White on navy', fg: '#FFFFFF', bg: '#14213D', mark: '#2F4A85', accent: '#FFFFFF', accentInk: '#14213D', chrome: 'dark' },
]

export type FontId =
  | 'hyperlegible'
  | 'lexend'
  | 'opendyslexic'
  | 'andika'
  | 'inclusive-sans'
  | 'verdana'
  | 'comic'
  | 'system'
  | 'serif'

export interface ReaderFont {
  id: FontId
  label: string
  /** One line on who the face was designed for, shown in the picker. */
  hint: string
  stack: string
}

/**
 * Faces bundled with the app (via @fontsource) are always available; the
 * others use whatever the device has, with a bundled or generic fallback.
 */
export const FONTS: ReaderFont[] = [
  {
    id: 'hyperlegible',
    label: 'Atkinson Hyperlegible',
    hint: 'Made for low vision. Letters that look alike, such as I, l and 1, are easy to tell apart.',
    stack: '"Atkinson Hyperlegible", system-ui, sans-serif',
  },
  {
    id: 'lexend',
    label: 'Lexend',
    hint: 'Wide letters and generous spacing, designed to make reading faster and less tiring.',
    stack: 'Lexend, system-ui, sans-serif',
  },
  {
    id: 'opendyslexic',
    label: 'OpenDyslexic',
    hint: 'Heavy bottoms on each letter help stop letters flipping or swapping for dyslexic readers.',
    stack: 'OpenDyslexic, system-ui, sans-serif',
  },
  {
    id: 'andika',
    label: 'Andika',
    hint: 'Simple, unambiguous letter shapes made for new and struggling readers.',
    stack: 'Andika, system-ui, sans-serif',
  },
  {
    id: 'inclusive-sans',
    label: 'Inclusive Sans',
    hint: 'Open, evenly spaced shapes that stay clear at small sizes and on screens.',
    stack: '"Inclusive Sans", system-ui, sans-serif',
  },
  {
    id: 'verdana',
    label: 'Verdana',
    hint: 'Wide letters with a tall x-height, often recommended in low-vision guidelines.',
    stack: 'Verdana, "DejaVu Sans", Geneva, sans-serif',
  },
  {
    id: 'comic',
    label: 'Comic Sans',
    hint: 'Handwriting-like shapes that many dyslexic readers find easier to follow.',
    stack: '"Comic Sans MS", "Comic Neue", sans-serif',
  },
  {
    id: 'system',
    label: 'System sans-serif',
    hint: 'The typeface your device already uses everywhere.',
    stack: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  },
  {
    id: 'serif',
    label: 'Serif',
    hint: 'Georgia or Times, for readers who prefer print-style letters.',
    stack: 'Georgia, "Times New Roman", serif',
  },
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

/** CSS custom properties that style any reading surface from the current settings. */
export function readerStyleVars(settings: Settings): Record<`--${string}`, string | number> {
  const theme = themeById(settings.themeId)
  const font = fontById(settings.fontId)
  return {
    '--reader-fg': theme.fg,
    '--reader-bg': theme.bg,
    '--reader-mark': theme.mark,
    '--reader-size': `${settings.fontSize}px`,
    '--reader-font': font.stack,
    '--reader-leading': LINE_SPACING[settings.lineSpacing],
    '--reader-tracking': `${settings.letterSpacing}em`,
    '--reader-weight': settings.bold ? 700 : 400,
  }
}

/**
 * CSS custom properties for the whole interface: chrome colours mixed from the
 * reading theme, the reading typeface, and a scale factor so controls and UI
 * text grow with the reading size (1× at the default size, capped at 1.5×).
 */
export function interfaceStyleVars(settings: Settings): Record<`--${string}`, string> {
  const theme = themeById(settings.themeId)
  const font = fontById(settings.fontId)
  const mix = (fgPct: number) => `color-mix(in srgb, ${theme.fg} ${fgPct}%, ${theme.bg})`
  const scale = clamp(settings.fontSize / DEFAULT_SETTINGS.fontSize, 1, 1.5)
  return {
    '--ink': theme.fg,
    '--ink-2': mix(78),
    '--ground': theme.bg,
    '--ground-2': mix(7),
    '--ground-3': mix(14),
    '--line': mix(40),
    '--line-strong': theme.fg,
    '--accent': theme.accent,
    '--accent-ink': theme.accentInk,
    '--focus': theme.accent,
    '--focus-halo': theme.bg,
    '--font-ui': font.stack,
    '--ui-scale': scale.toFixed(3),
  }
}

export function themeById(id: ThemeId): ReaderTheme {
  return THEMES.find((t) => t.id === id) ?? THEMES[0]
}

export function fontById(id: FontId): ReaderFont {
  return FONTS.find((f) => f.id === id) ?? FONTS[0]
}
