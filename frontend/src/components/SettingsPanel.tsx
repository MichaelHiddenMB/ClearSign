import { useEffect, useRef } from 'react'
import { FONTS, FONT_SIZE_MAX, FONT_SIZE_MIN, FONT_SIZE_STEP, THEMES, type LineSpacing, type Settings } from '../lib/settings'
import { Icon } from './Icon'

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
  settings: Settings
  onChange: (patch: Partial<Settings>) => void
  voices: SpeechSynthesisVoice[]
  speechSupported: boolean
  onPreviewVoice: () => void
}

const SPACING_OPTIONS: { id: LineSpacing; label: string }[] = [
  { id: 'compact', label: 'Compact' },
  { id: 'normal', label: 'Normal' },
  { id: 'loose', label: 'Loose' },
]

export function SettingsPanel({ open, onClose, settings, onChange, voices, speechSupported, onPreviewVoice }: SettingsPanelProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog ref={dialogRef} className="panel" aria-labelledby="panel-title" onClose={onClose}>
      <form method="dialog" className="panel__form">
        <header className="panel__header">
          <h2 id="panel-title">Display &amp; speech</h2>
          <button type="submit" className="btn btn--icon" aria-label="Close">
            <Icon name="close" />
          </button>
        </header>

        <fieldset className="panel__section">
          <legend>Colours</legend>
          <div className="swatches">
            {THEMES.map((t) => (
              <label key={t.id} className="swatch" style={{ color: t.fg, background: t.bg }}>
                <input
                  type="radio"
                  name="theme"
                  id={`theme-${t.id}`}
                  value={t.id}
                  checked={settings.themeId === t.id}
                  onChange={() => onChange({ themeId: t.id })}
                />
                <span className="swatch__sample" aria-hidden="true">Aa</span>
                <span className="swatch__label">{t.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="panel__section">
          <legend>Text</legend>
          <div className="field">
            <label htmlFor="font-size">Size</label>
            <div className="field__control">
              <input
                id="font-size"
                type="range"
                min={FONT_SIZE_MIN}
                max={FONT_SIZE_MAX}
                step={FONT_SIZE_STEP}
                value={settings.fontSize}
                onChange={(e) => onChange({ fontSize: Number(e.target.value) })}
              />
              <output htmlFor="font-size">{settings.fontSize}px</output>
            </div>
          </div>

          <div className="field">
            <label htmlFor="font-family">Typeface</label>
            <select id="font-family" value={settings.fontId} onChange={(e) => onChange({ fontId: e.target.value as Settings['fontId'] })}>
              {FONTS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <span className="field__label" id="spacing-label">Line spacing</span>
            <div className="segmented" role="group" aria-labelledby="spacing-label">
              {SPACING_OPTIONS.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  aria-pressed={settings.lineSpacing === o.id}
                  onClick={() => onChange({ lineSpacing: o.id })}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label htmlFor="letter-spacing">Letter spacing</label>
            <div className="field__control">
              <input
                id="letter-spacing"
                type="range"
                min={0}
                max={0.2}
                step={0.05}
                value={settings.letterSpacing}
                onChange={(e) => onChange({ letterSpacing: Number(e.target.value) })}
              />
              <output htmlFor="letter-spacing">{settings.letterSpacing === 0 ? 'Normal' : `+${Math.round(settings.letterSpacing * 100)}%`}</output>
            </div>
          </div>

          <div className="field field--row">
            <label htmlFor="bold">Bold text</label>
            <input id="bold" type="checkbox" className="switch" checked={settings.bold} onChange={(e) => onChange({ bold: e.target.checked })} />
          </div>
        </fieldset>

        <fieldset className="panel__section">
          <legend>Read aloud</legend>
          {speechSupported ? (
            <>
              <div className="field">
                <label htmlFor="speech-rate">Speed</label>
                <div className="field__control">
                  <input
                    id="speech-rate"
                    type="range"
                    min={0.5}
                    max={1.5}
                    step={0.1}
                    value={settings.speechRate}
                    onChange={(e) => onChange({ speechRate: Number(e.target.value) })}
                  />
                  <output htmlFor="speech-rate">{settings.speechRate.toFixed(1)}×</output>
                </div>
              </div>
              <div className="field">
                <label htmlFor="voice">Voice</label>
                <select id="voice" value={settings.voiceURI} onChange={(e) => onChange({ voiceURI: e.target.value })}>
                  <option value="">Browser default</option>
                  {voices.map((v) => (
                    <option key={v.voiceURI} value={v.voiceURI}>
                      {v.name} ({v.lang})
                    </option>
                  ))}
                </select>
              </div>
              <button type="button" className="btn" onClick={onPreviewVoice}>
                <Icon name="play" />
                <span>Hear a sample</span>
              </button>
            </>
          ) : (
            <p className="panel__note">This browser doesn't support speech. Try Safari, Chrome or Edge.</p>
          )}
        </fieldset>

        <footer className="panel__footer">
          <button type="submit" className="btn btn--primary">
            Done
          </button>
        </footer>
      </form>
    </dialog>
  )
}
