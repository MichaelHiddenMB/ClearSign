import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { FONTS, fontById, type FontId } from '../lib/settings'
import { Icon } from './Icon'

interface FontSelectProps {
  value: FontId
  onChange: (id: FontId) => void
  labelId: string
}

/**
 * A select whose options render in their own typeface, following the
 * WAI-ARIA select-only combobox pattern: the button is the combobox, the
 * popup is a listbox, and keyboard focus stays on the button while
 * aria-activedescendant tracks the highlighted option.
 */
export function FontSelect({ value, onChange, labelId }: FontSelectProps) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(() => FONTS.findIndex((f) => f.id === value))
  const wrapper = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const baseId = useId()
  const listId = `${baseId}-list`
  const optionId = (i: number) => `${baseId}-opt-${FONTS[i].id}`
  const current = fontById(value)

  const show = () => {
    setActive(FONTS.findIndex((f) => f.id === value))
    setOpen(true)
  }
  const hide = () => setOpen(false)
  const choose = (i: number) => {
    onChange(FONTS[i].id)
    hide()
  }

  // Close on a click outside.
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (!wrapper.current?.contains(e.target as Node)) hide()
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  // Keep the highlighted option in view.
  useEffect(() => {
    if (!open) return
    list.current?.querySelector<HTMLElement>(`#${CSS.escape(optionId(active))}`)?.scrollIntoView({ block: 'nearest' })
  })

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const last = FONTS.length - 1
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault()
        show()
      }
      return
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActive((i) => Math.min(last, i + 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(0, i - 1))
        break
      case 'Home':
        e.preventDefault()
        setActive(0)
        break
      case 'End':
        e.preventDefault()
        setActive(last)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        choose(active)
        break
      case 'Escape':
        e.preventDefault()
        e.stopPropagation()
        hide()
        break
      case 'Tab':
        hide()
        break
    }
  }

  return (
    <div ref={wrapper} className="font-select">
      <button
        type="button"
        className="font-select__button"
        role="combobox"
        aria-labelledby={labelId}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? optionId(active) : undefined}
        onClick={() => (open ? hide() : show())}
        onKeyDown={onKeyDown}
        style={{ fontFamily: current.stack }}
      >
        <span className="font-select__text">
          <span className="font-select__name">{current.label}</span>
          <span className="font-select__hint">{current.hint}</span>
        </span>
        <Icon name="chevron-down" />
      </button>

      {open && (
        <ul ref={list} id={listId} className="font-select__list" role="listbox" aria-labelledby={labelId} tabIndex={-1}>
          {FONTS.map((f, i) => (
            <li
              key={f.id}
              id={optionId(i)}
              role="option"
              aria-selected={f.id === value}
              data-active={i === active || undefined}
              className="font-select__option"
              style={{ fontFamily: f.stack }}
              onPointerMove={() => setActive(i)}
              onClick={() => choose(i)}
            >
              <span className="font-select__name">{f.label}</span>
              <span className="font-select__hint">{f.hint}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
