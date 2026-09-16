import { useEffect, useRef, type KeyboardEvent } from 'react'
import type { Capture } from '../hooks/useCaptures'
import { panelId, tabId } from '../lib/captureIds'
import { Icon } from './Icon'

interface CaptureTabsProps {
  captures: Capture[]
  activeId: number | null
  onSelect: (id: number) => void
  onClose: (id: number) => void
}

/** One tab per capture taken this session, so earlier signs stay a tap away. */
export function CaptureTabs({ captures, activeId, onSelect, onClose }: CaptureTabsProps) {
  const list = useRef<HTMLDivElement>(null)

  // The strip scrolls sideways on phones; keep the selected tab in view.
  useEffect(() => {
    list.current
      ?.querySelector<HTMLButtonElement>('[role="tab"][aria-selected="true"]')
      ?.scrollIntoView({ inline: 'nearest', block: 'nearest' })
  }, [activeId])

  const focusTab = (index: number) => {
    const tabs = list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
    tabs?.[index]?.focus()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = captures.length - 1
    let target: number | null = null
    switch (e.key) {
      case 'ArrowRight':
        target = Math.min(last, index + 1)
        break
      case 'ArrowLeft':
        target = Math.max(0, index - 1)
        break
      case 'Home':
        target = 0
        break
      case 'End':
        target = last
        break
      case 'Delete':
      case 'Backspace':
        e.preventDefault()
        close(captures[index].id)
        return
      default:
        return
    }
    e.preventDefault()
    onSelect(captures[target].id)
    focusTab(target)
  }

  const close = (id: number) => {
    onClose(id)
    // The closed tab's buttons disappear; keep keyboard focus in the strip.
    requestAnimationFrame(() => {
      const selected = list.current?.querySelector<HTMLButtonElement>('[role="tab"][aria-selected="true"]')
      selected?.focus()
    })
  }

  return (
    <div ref={list} className="tabs" role="tablist" aria-label="Captures">
      {captures.map((capture, index) => {
        const selected = capture.id === activeId
        return (
          <button
            key={capture.id}
            type="button"
            role="tab"
            id={tabId(capture.id)}
            className="tab"
            aria-selected={selected}
            aria-controls={panelId(capture.id)}
            aria-description="Press Delete to close"
            tabIndex={selected ? 0 : -1}
            onClick={(e) => {
              // The × at the end of the tab closes it; anywhere else selects it.
              if ((e.target as HTMLElement).closest('.tab__close')) close(capture.id)
              else onSelect(capture.id)
            }}
            onKeyDown={(e) => onKeyDown(e, index)}
          >
            <span className="tab__index" aria-hidden="true">{index + 1}</span>
            <span className="visually-hidden">Capture {index + 1}: </span>
            <span className="tab__label">{labelFor(capture)}</span>
            <span className="tab__close" aria-hidden="true" title={`Close capture ${index + 1}`}>
              <Icon name="close" size={20} />
            </span>
          </button>
        )
      })}
    </div>
  )
}

function labelFor(capture: Capture): string {
  if (capture.status === 'empty') return 'New'
  if (capture.status === 'recognizing') return 'Reading…'
  const first = capture.result?.lines[0]?.text
  if (capture.status === 'error' || !first) return 'No text'
  return first.length > 18 ? `${first.slice(0, 17)}…` : first
}
