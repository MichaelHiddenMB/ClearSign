import { useEffect, type RefObject } from 'react'
import type { CameraState } from '../hooks/useCamera'
import { Icon } from './Icon'

interface ViewfinderProps {
  videoRef: RefObject<HTMLVideoElement | null>
  cameraState: CameraState
  busy: boolean
  onStart: () => void
  onCapture: () => void
}

const CAMERA_MESSAGES: Partial<Record<CameraState, { title: string; body: string }>> = {
  idle: {
    title: 'Camera is off',
    body: 'Turn on the camera, then point it at a sign, menu, label or notice.',
  },
  denied: {
    title: 'Camera access was blocked',
    body: 'Allow camera access for this site in your browser settings, then try again.',
  },
  unavailable: {
    title: 'No camera found',
    body: 'ClearSign needs a camera to read signs. Open it on a phone or a device with a camera.',
  },
  error: {
    title: 'The camera could not start',
    body: 'Close other apps that may be using the camera, then try again.',
  },
}

export function Viewfinder({ videoRef, cameraState, busy, onStart, onCapture }: ViewfinderProps) {
  const live = cameraState === 'live'
  const message = CAMERA_MESSAGES[cameraState]

  // Space or Enter anywhere on the capture screen takes a photo, so a user
  // holding the phone at arm's length does not have to find the button.
  useEffect(() => {
    if (!live) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== ' ' || e.target instanceof HTMLButtonElement || e.target instanceof HTMLInputElement) return
      e.preventDefault()
      if (!busy) onCapture()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [live, busy, onCapture])

  return (
    <section className="viewfinder" aria-labelledby="viewfinder-heading">
      <h2 id="viewfinder-heading" className="visually-hidden">
        Camera
      </h2>

      <div className="viewfinder__frame" data-live={live || undefined}>
        <video ref={videoRef} className="viewfinder__video" playsInline muted aria-label="Live camera preview" />
        {live && (
          <div className="viewfinder__guides" aria-hidden="true">
            <span /><span /><span /><span />
          </div>
        )}
        {!live && message && (
          <div className="viewfinder__notice" role="status">
            <p className="viewfinder__notice-title">{message.title}</p>
            <p>{message.body}</p>
          </div>
        )}
        {cameraState === 'starting' && (
          <div className="viewfinder__notice" role="status">
            <p className="viewfinder__notice-title">Starting camera…</p>
          </div>
        )}
      </div>

      <div className="viewfinder__actions">
        {live ? (
          <button type="button" className="btn btn--primary btn--capture" onClick={onCapture} disabled={busy}>
            <Icon name="camera" size={28} />
            <span>{busy ? 'Reading…' : 'Capture'}</span>
          </button>
        ) : (
          <button
            type="button"
            className="btn btn--primary btn--capture"
            onClick={onStart}
            disabled={busy || cameraState === 'starting' || cameraState === 'unavailable'}
          >
            <Icon name="camera" size={28} />
            <span>{cameraState === 'denied' || cameraState === 'error' ? 'Try camera again' : 'Turn on camera'}</span>
          </button>
        )}
      </div>

      {live && (
        <p className="viewfinder__hint">
          Fill the frame with the text. Press <kbd>Space</kbd> to capture.
        </p>
      )}
    </section>
  )
}
