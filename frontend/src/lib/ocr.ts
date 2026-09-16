export interface OcrLine {
  text: string
  /** Mean Tesseract word confidence for the line, 0–100. */
  confidence: number
}

export interface OcrResult {
  lines: OcrLine[]
  /** Number of words the service discarded for low confidence. */
  droppedWords: number
  /** Server-side processing time in milliseconds, when reported. */
  processingMs?: number
  /** Whether this came from the live service or from the built-in sample. */
  source: 'service' | 'sample'
}

export class OcrError extends Error {
  readonly kind: 'network' | 'server' | 'empty'

  constructor(kind: OcrError['kind'], message: string) {
    super(message)
    this.name = 'OcrError'
    this.kind = kind
  }
}

const ENDPOINT = '/api/ocr'
const USE_SAMPLE = import.meta.env.VITE_OCR_MOCK === 'true'

/**
 * Sends a captured frame to the FastAPI service and returns the recognised lines.
 * The service preprocesses with OpenCV (grayscale, adaptive threshold, deskew)
 * and runs Tesseract, dropping words below its confidence threshold.
 *
 * In development, a network failure falls back to a sample result so the reader
 * can be exercised without the Python service running. The result is labelled.
 */
export async function recognizeText(image: Blob, signal?: AbortSignal): Promise<OcrResult> {
  if (USE_SAMPLE) return sampleResult()

  const body = new FormData()
  body.append('image', image, 'frame.jpg')

  let response: Response
  try {
    response = await fetch(ENDPOINT, { method: 'POST', body, signal })
  } catch (err) {
    if (signal?.aborted) throw err
    if (import.meta.env.DEV) return sampleResult()
    throw new OcrError('network', 'The text recognition service could not be reached. Check your connection and try again.')
  }

  if (import.meta.env.DEV && [502, 503, 504].includes(response.status)) {
    // The dev proxy answers 502 when the FastAPI service is not running.
    return sampleResult()
  }

  if (!response.ok) {
    throw new OcrError('server', `The text recognition service returned an error (HTTP ${response.status}). Try again in a moment.`)
  }

  const payload = (await response.json()) as {
    lines?: OcrLine[]
    dropped_words?: number
    processing_ms?: number
  }

  const lines = (payload.lines ?? []).filter((l) => l.text.trim().length > 0)
  if (lines.length === 0) {
    throw new OcrError('empty', 'No readable text was found. Move closer, hold the camera steady, and make sure the sign is well lit.')
  }

  return {
    lines,
    droppedWords: payload.dropped_words ?? 0,
    processingMs: payload.processing_ms,
    source: 'service',
  }
}

function sampleResult(): Promise<OcrResult> {
  const lines: OcrLine[] = [
    { text: 'PLATFORM 2', confidence: 96 },
    { text: 'Trains to Downtown', confidence: 93 },
    { text: 'Next departure 4:12 PM', confidence: 91 },
    { text: 'Stand behind the yellow line', confidence: 88 },
  ]
  return new Promise((resolve) => {
    setTimeout(() => resolve({ lines, droppedWords: 2, processingMs: 640, source: 'sample' }), 900)
  })
}
