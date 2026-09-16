import { useCallback, useEffect, useRef, useState } from 'react'
import { Reader, type RecognitionStatus } from './components/Reader'
import { SettingsPanel } from './components/SettingsPanel'
import { TopBar, type View } from './components/TopBar'
import { Viewfinder } from './components/Viewfinder'
import { useCamera } from './hooks/useCamera'
import { useSettings } from './hooks/useSettings'
import { useSpeech } from './hooks/useSpeech'
import { grabFrame } from './lib/capture'
import { OcrError, recognizeText, type OcrResult } from './lib/ocr'

export default function App() {
  const { settings, update } = useSettings()
  const camera = useCamera()
  const speech = useSpeech()

  const [view, setView] = useState<View>('capture')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [status, setStatus] = useState<RecognitionStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [result, setResult] = useState<OcrResult | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Release the previous object URL whenever a new frame replaces it.
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl) }, [imageUrl])

  const recognize = useCallback(
    async (image: Blob) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      speech.stop()
      setImageUrl(URL.createObjectURL(image))
      setResult(null)
      setErrorMessage(null)
      setStatus('recognizing')
      setView('read')

      try {
        const next = await recognizeText(image, controller.signal)
        if (controller.signal.aborted) return
        setResult(next)
        setStatus('done')
      } catch (err) {
        if (controller.signal.aborted) return
        setErrorMessage(err instanceof OcrError ? err.message : 'Something went wrong while reading the image. Try again.')
        setStatus('error')
      }
    },
    [speech],
  )

  const capture = async () => {
    const video = camera.videoRef.current
    if (!video) return
    try {
      const frame = await grabFrame(video)
      await recognize(frame)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not capture a frame.')
      setStatus('error')
      setView('read')
    }
  }

  const retake = useCallback(() => {
    abortRef.current?.abort()
    speech.stop()
    setStatus('idle')
    setResult(null)
    setErrorMessage(null)
    setView('capture')
  }, [speech])

  const readAloud = useCallback(() => {
    if (!result) return
    speech.speak(
      result.lines.map((l) => l.text),
      { rate: settings.speechRate, voiceURI: settings.voiceURI },
    )
  }, [result, settings.speechRate, settings.voiceURI, speech])

  const previewVoice = useCallback(() => {
    speech.speak(['This is how ClearSign will read signs to you.'], { rate: settings.speechRate, voiceURI: settings.voiceURI })
  }, [settings.speechRate, settings.voiceURI, speech])

  const busy = status === 'recognizing'

  return (
    <div className="app" data-view={view}>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>

      <TopBar view={view} onViewChange={setView} hasResult={status === 'done'} onOpenSettings={() => setSettingsOpen(true)} />

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
          status={status}
          errorMessage={errorMessage}
          result={result}
          imageUrl={imageUrl}
          speechSupported={speech.supported}
          speechStatus={speech.status}
          speechPosition={speech.position}
          onSpeak={readAloud}
          onPause={speech.pause}
          onResume={speech.resume}
          onStop={speech.stop}
          onRetake={retake}
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
