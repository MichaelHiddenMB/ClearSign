import { useCallback, useState } from 'react'
import { Reader } from './components/Reader'
import { SettingsPanel } from './components/SettingsPanel'
import { TopBar, type View } from './components/TopBar'
import { Viewfinder } from './components/Viewfinder'
import { useCamera } from './hooks/useCamera'
import { useCaptures } from './hooks/useCaptures'
import { useSettings } from './hooks/useSettings'
import { useSpeech } from './hooks/useSpeech'
import { grabFrame } from './lib/capture'
import { OcrError, recognizeText } from './lib/ocr'

export default function App() {
  const { settings, update } = useSettings()
  const camera = useCamera()
  const speech = useSpeech()
  const captures = useCaptures()

  const [view, setView] = useState<View>('capture')
  const [settingsOpen, setSettingsOpen] = useState(false)

  const recognize = useCallback(
    async (image: Blob) => {
      speech.stop()
      const id = captures.add(image)
      setView('read')
      try {
        const result = await recognizeText(image)
        captures.update(id, { status: 'done', result })
      } catch (err) {
        captures.update(id, {
          status: 'error',
          errorMessage: err instanceof OcrError ? err.message : 'Something went wrong while reading the image. Try again.',
        })
      }
    },
    [captures, speech],
  )

  const capture = async () => {
    const video = camera.videoRef.current
    if (!video) return
    try {
      const frame = await grabFrame(video)
      await recognize(frame)
    } catch (err) {
      const id = captures.add(new Blob())
      captures.update(id, { status: 'error', errorMessage: err instanceof Error ? err.message : 'Could not capture a frame.' })
      setView('read')
    }
  }

  // "Capture another" keeps the current text in its tab and returns to the camera.
  const captureAnother = useCallback(() => {
    speech.stop()
    setView('capture')
  }, [speech])

  const selectCapture = useCallback(
    (id: number) => {
      speech.stop()
      captures.select(id)
    },
    [captures, speech],
  )

  const closeCapture = useCallback(
    (id: number) => {
      if (id === captures.activeId) speech.stop()
      captures.remove(id)
    },
    [captures, speech],
  )

  const active = captures.active
  const readAloud = useCallback(() => {
    if (!active?.result) return
    speech.speak(
      active.result.lines.map((l) => l.text),
      { rate: settings.speechRate, voiceURI: settings.voiceURI },
    )
  }, [active, settings.speechRate, settings.voiceURI, speech])

  const previewVoice = useCallback(() => {
    speech.speak(['This is how ClearSign will read signs to you.'], { rate: settings.speechRate, voiceURI: settings.voiceURI })
  }, [settings.speechRate, settings.voiceURI, speech])

  const busy = captures.latest?.status === 'recognizing'

  return (
    <div className="app" data-view={view}>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>

      <TopBar
        view={view}
        onViewChange={setView}
        hasResult={captures.list.some((c) => c.status === 'done')}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <main id="main" className="workspace">
        <Viewfinder
          videoRef={camera.videoRef}
          cameraState={camera.state}
          busy={busy}
          onStart={camera.start}
          onCapture={capture}
          onFile={recognize}
        />
        <Reader
          settings={settings}
          onSettingsChange={update}
          captures={captures.list}
          activeId={captures.activeId}
          status={active?.status ?? 'idle'}
          errorMessage={active?.errorMessage ?? null}
          result={active?.result ?? null}
          imageUrl={active?.imageUrl ?? null}
          speechSupported={speech.supported}
          speechStatus={speech.status}
          speechPosition={speech.position}
          onSpeak={readAloud}
          onPause={speech.pause}
          onResume={speech.resume}
          onStop={speech.stop}
          onRetake={captureAnother}
          onSelectCapture={selectCapture}
          onCloseCapture={closeCapture}
        />
      </main>

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onChange={update}
        voices={speech.voices}
        speechSupported={speech.supported}
        onPreviewVoice={previewVoice}
      />
    </div>
  )
}
