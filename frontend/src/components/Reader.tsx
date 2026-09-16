import { useEffect, useRef, useState } from 'react'
import type { SpeechPosition, SpeechStatus } from '../hooks/useSpeech'
import type { OcrResult } from '../lib/ocr'
import {
  FONT_SIZE_MAX,
  FONT_SIZE_MIN,
  FONT_SIZE_STEP,
  LINE_SPACING,
  fontById,
  themeById,
  type Settings,
} from '../lib/settings'
import { Icon } from './Icon'

export type RecognitionStatus = 'idle' | 'recognizing' | 'done' | 'error'

interface ReaderProps {
  settings: Settings
  onSettingsChange: (patch: Partial<Settings>) => void
  status: RecognitionStatus
  errorMessage: string | null
  result: OcrResult | null
  imageUrl: string | null
  speechSupported: boolean
  speechStatus: SpeechStatus
  speechPosition: SpeechPosition | null
  onSpeak: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  onRetake: () => void
}

type Mode = 'text' | 'photo'
const ZOOM_LEVELS = [1, 1.5, 2, 3, 4]

export function Reader(props: ReaderProps) {
  const { settings, onSettingsChange, status, errorMessage, result, imageUrl } = props
  const { speechSupported, speechStatus, speechPosition, onSpeak, onPause, onResume, onStop, onRetake } = props

  const [mode, setMode] = useState<Mode>('text')
  const [zoom, setZoom] = useState(1)
  const theme = themeById(settings.themeId)
  const font = fontById(settings.fontId)
  const hasText = status === 'done' && result !== null

  const activeLine = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    activeLine.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [speechPosition?.line])

  // A fresh capture always opens in the text view at 1x.
  const [seenImageUrl, setSeenImageUrl] = useState(imageUrl)
  if (imageUrl !== seenImageUrl) {
    setSeenImageUrl(imageUrl)
    setMode('text')
    setZoom(1)
  }

  const step = (direction: 1 | -1) => {
    const next = Math.min(FONT_SIZE_MAX, Math.max(FONT_SIZE_MIN, settings.fontSize + direction * FONT_SIZE_STEP))
    onSettingsChange({ fontSize: next })
  }

  const surfaceStyle = {
    '--reader-fg': theme.fg,
    '--reader-bg': theme.bg,
    '--reader-mark': theme.mark,
    '--reader-size': `${settings.fontSize}px`,
    '--reader-font': font.stack,
    '--reader-leading': LINE_SPACING[settings.lineSpacing],
    '--reader-tracking': `${settings.letterSpacing}em`,
    '--reader-weight': settings.bold ? 700 : 400,
  } as React.CSSProperties

  return (
    <section className="reader" aria-labelledby="reader-heading">
      <h2 id="reader-heading" className="visually-hidden">
        Recognised text
      </h2>

      <div className="toolbar" role="toolbar" aria-label="Reading controls">
        <div className="toolbar__group" role="group" aria-label="Text size">
          <button
            type="button"
            className="btn btn--icon"
            onClick={() => step(-1)}
            disabled={settings.fontSize <= FONT_SIZE_MIN}
            aria-label="Smaller text"
          >
            <Icon name="minus" />
            <span aria-hidden="true">A</span>
          </button>
          <output className="toolbar__value" aria-live="polite" aria-label="Text size">
            {settings.fontSize}<small>px</small>
          </output>
          <button
            type="button"
            className="btn btn--icon"
            onClick={() => step(1)}
            disabled={settings.fontSize >= FONT_SIZE_MAX}
            aria-label="Larger text"
          >
            <Icon name="plus" />
            <span aria-hidden="true">A</span>
          </button>
        </div>

        {speechSupported && (
          <div className="toolbar__group" role="group" aria-label="Read aloud">
            {speechStatus === 'idle' && (
              <button type="button" className="btn btn--icon" onClick={onSpeak} disabled={!hasText}>
                <Icon name="play" />
                <span>Read aloud</span>
              </button>
            )}
            {speechStatus === 'speaking' && (
              <button type="button" className="btn btn--icon" onClick={onPause}>
                <Icon name="pause" />
                <span>Pause</span>
              </button>
            )}
            {speechStatus === 'paused' && (
              <button type="button" className="btn btn--icon" onClick={onResume}>
                <Icon name="play" />
                <span>Resume</span>
              </button>
            )}
            <button
              type="button"
              className="btn btn--icon"
              onClick={onStop}
              disabled={speechStatus === 'idle'}
              aria-label="Stop reading"
            >
              <Icon name="stop" />
            </button>
          </div>
        )}

        {imageUrl && (
          <div className="toolbar__group toolbar__group--end" role="group" aria-label="View">
            <button
              type="button"
              className="btn btn--icon"
              aria-pressed={mode === 'text'}
              onClick={() => setMode('text')}
            >
              <Icon name="text" />
              <span>Text</span>
            </button>
            <button
              type="button"
              className="btn btn--icon"
              aria-pressed={mode === 'photo'}
              onClick={() => setMode('photo')}
            >
              <Icon name="image" />
              <span>Photo</span>
            </button>
          </div>
        )}
      </div>

      {mode === 'photo' && imageUrl ? (
        <div className="photo">
          <div className="photo__controls" role="group" aria-label="Zoom">
            <button
              type="button"
              className="btn btn--icon"
              onClick={() => setZoom((z) => ZOOM_LEVELS[Math.max(0, ZOOM_LEVELS.indexOf(z) - 1)])}
              disabled={zoom === ZOOM_LEVELS[0]}
              aria-label="Zoom out"
            >
              <Icon name="zoom-out" />
            </button>
            <output className="toolbar__value" aria-label="Zoom level">
              {zoom}×
            </output>
            <button
              type="button"
              className="btn btn--icon"
              onClick={() => setZoom((z) => ZOOM_LEVELS[Math.min(ZOOM_LEVELS.length - 1, ZOOM_LEVELS.indexOf(z) + 1)])}
              disabled={zoom === ZOOM_LEVELS[ZOOM_LEVELS.length - 1]}
              aria-label="Zoom in"
            >
              <Icon name="zoom-in" />
            </button>
          </div>
          <div className="photo__scroll">
            <img src={imageUrl} alt="The photo you captured" style={{ width: `${zoom * 100}%` }} />
          </div>
        </div>
      ) : (
        <article className="surface" style={surfaceStyle} aria-live="polite" aria-busy={status === 'recognizing'}>
          {status === 'idle' && (
            <div className="surface__empty">
              <p className="surface__lede">Nothing captured yet.</p>
              <p>
                Point the camera at a sign, menu, or label and press <strong>Capture</strong>. The text will appear here,
                enlarged and in your chosen colours.
              </p>
            </div>
          )}

          {status === 'recognizing' && (
            <div className="surface__empty">
              <p className="surface__lede">Reading the text…</p>
              <p>Hold on for a moment.</p>
            </div>
          )}

          {status === 'error' && (
            <div className="surface__empty">
              <p className="surface__lede">Couldn't read that</p>
              <p>{errorMessage}</p>
              <button type="button" className="btn" onClick={onRetake}>
                <Icon name="retake" />
                <span>Try again</span>
              </button>
            </div>
          )}

          {hasText && (
            <>
              {result.lines.map((line, i) => {
                const isActive = speechPosition?.line === i
                return (
                  <p key={i} className="surface__line" data-active={isActive || undefined} ref={isActive ? activeLine : null}>
                    {isActive && speechPosition && speechPosition.charLength > 0
                      ? highlight(line.text, speechPosition.charIndex, speechPosition.charLength)
                      : line.text}
                  </p>
                )
              })}
              <footer className="surface__meta">
                {result.source === 'sample' && <span className="chip chip--warn">Sample text · recognition service is offline</span>}
                <span>
                  {result.lines.length} {result.lines.length === 1 ? 'line' : 'lines'}
                  {result.droppedWords > 0 && `, ${result.droppedWords} unclear ${result.droppedWords === 1 ? 'word' : 'words'} left out`}
                </span>
                <button type="button" className="btn btn--quiet" onClick={onRetake}>
                  <Icon name="retake" />
                  <span>Capture another</span>
                </button>
              </footer>
            </>
          )}
        </article>
      )}
    </section>
  )
}

function highlight(text: string, start: number, length: number) {
  const end = Math.min(text.length, start + length)
  return (
    <>
      {text.slice(0, start)}
      <mark>{text.slice(start, end)}</mark>
      {text.slice(end)}
    </>
  )
}
