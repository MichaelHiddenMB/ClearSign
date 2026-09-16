import { useCallback, useEffect, useRef, useState } from 'react'

export interface SpeechPosition {
  line: number
  charIndex: number
  charLength: number
}

export type SpeechStatus = 'idle' | 'speaking' | 'paused'

interface SpeakOptions {
  rate: number
  voiceURI: string
}

/**
 * Reads lines aloud with the Web Speech API, one utterance per line.
 * Speaking line-by-line keeps each utterance short (long utterances are cut off
 * in some browsers) and gives the reader a natural unit to highlight.
 */
export function useSpeech() {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [status, setStatus] = useState<SpeechStatus>('idle')
  const [position, setPosition] = useState<SpeechPosition | null>(null)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const sessionRef = useRef(0)

  useEffect(() => {
    if (!supported) return
    const load = () => setVoices(window.speechSynthesis.getVoices())
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [supported])

  const stop = useCallback(() => {
    if (!supported) return
    sessionRef.current += 1
    window.speechSynthesis.cancel()
    setStatus('idle')
    setPosition(null)
  }, [supported])

  const speak = useCallback(
    (lines: string[], { rate, voiceURI }: SpeakOptions) => {
      if (!supported || lines.length === 0) return
      stop()
      const session = ++sessionRef.current
      const voice = voices.find((v) => v.voiceURI === voiceURI) ?? null
      setStatus('speaking')

      const speakLine = (index: number) => {
        if (session !== sessionRef.current) return
        if (index >= lines.length) {
          setStatus('idle')
          setPosition(null)
          return
        }
        const utterance = new SpeechSynthesisUtterance(lines[index])
        utterance.rate = rate
        if (voice) utterance.voice = voice
        utterance.onstart = () => {
          if (session === sessionRef.current) setPosition({ line: index, charIndex: 0, charLength: 0 })
        }
        utterance.onboundary = (e) => {
          if (session !== sessionRef.current || e.name !== 'word') return
          setPosition({ line: index, charIndex: e.charIndex, charLength: e.charLength ?? 0 })
        }
        utterance.onend = () => speakLine(index + 1)
        utterance.onerror = (e) => {
          if (e.error === 'interrupted' || e.error === 'canceled') return
          speakLine(index + 1)
        }
        window.speechSynthesis.speak(utterance)
      }
      speakLine(0)
    },
    [supported, stop, voices],
  )

  const pause = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.pause()
    setStatus('paused')
  }, [supported])

  const resume = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.resume()
    setStatus('speaking')
  }, [supported])

  useEffect(() => () => stop(), [stop])

  return { supported, status, position, voices, speak, pause, resume, stop }
}
