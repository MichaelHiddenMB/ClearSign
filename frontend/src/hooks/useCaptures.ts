import { useCallback, useEffect, useReducer, useRef } from 'react'
import type { OcrResult } from '../lib/ocr'

export type CaptureStatus = 'recognizing' | 'done' | 'error'

export interface Capture {
  id: number
  /** Object URL of the captured frame; released when the capture is closed. */
  imageUrl: string
  status: CaptureStatus
  result: OcrResult | null
  errorMessage: string | null
  takenAt: number
}

/** Oldest captures are dropped beyond this so frames do not pile up in memory. */
export const MAX_CAPTURES = 12

interface State {
  list: Capture[]
  activeId: number | null
}

type Action =
  | { type: 'add'; capture: Capture }
  | { type: 'update'; id: number; patch: Partial<Capture> }
  | { type: 'remove'; id: number }
  | { type: 'select'; id: number }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'add': {
      const list = [...state.list, action.capture].slice(-MAX_CAPTURES)
      return { list, activeId: action.capture.id }
    }
    case 'update':
      return { ...state, list: state.list.map((c) => (c.id === action.id ? { ...c, ...action.patch } : c)) }
    case 'remove': {
      const index = state.list.findIndex((c) => c.id === action.id)
      if (index < 0) return state
      const list = state.list.filter((c) => c.id !== action.id)
      let activeId = state.activeId
      if (activeId === action.id) {
        // Prefer the capture taken just before the closed one, then the one after.
        const neighbour = list[index - 1] ?? list[index] ?? null
        activeId = neighbour ? neighbour.id : null
      }
      return { list, activeId }
    }
    case 'select':
      return state.list.some((c) => c.id === action.id) ? { ...state, activeId: action.id } : state
  }
}

let nextId = 1

/** The list of captures taken this session, one tab each, and which one is showing. */
export function useCaptures() {
  const [state, dispatch] = useReducer(reducer, { list: [], activeId: null })

  // Release object URLs once their capture has left the list (or on unmount).
  const urls = useRef(new Set<string>())
  useEffect(() => {
    const live = new Set(state.list.map((c) => c.imageUrl))
    for (const url of urls.current) if (!live.has(url)) URL.revokeObjectURL(url)
    urls.current = live
  }, [state.list])
  useEffect(() => () => { for (const url of urls.current) URL.revokeObjectURL(url) }, [])

  const add = useCallback((image: Blob): number => {
    const id = nextId++
    dispatch({
      type: 'add',
      capture: { id, imageUrl: URL.createObjectURL(image), status: 'recognizing', result: null, errorMessage: null, takenAt: Date.now() },
    })
    return id
  }, [])

  const update = useCallback((id: number, patch: Partial<Capture>) => dispatch({ type: 'update', id, patch }), [])
  const remove = useCallback((id: number) => dispatch({ type: 'remove', id }), [])
  const select = useCallback((id: number) => dispatch({ type: 'select', id }), [])

  const active = state.list.find((c) => c.id === state.activeId) ?? null
  const latest = state.list[state.list.length - 1] ?? null

  return { list: state.list, activeId: state.activeId, active, latest, add, update, remove, select }
}
