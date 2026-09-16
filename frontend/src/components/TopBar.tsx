import { Icon } from './Icon'

export type View = 'capture' | 'read'

interface TopBarProps {
  view: View
  onViewChange: (view: View) => void
  hasResult: boolean
  onOpenSettings: () => void
}

export function TopBar({ view, onViewChange, hasResult, onOpenSettings }: TopBarProps) {
  return (
    <header className="topbar">
      <h1 className="wordmark">
        Clear<span>Sign</span>
      </h1>

      <nav className="views" aria-label="Screens">
        <button
          type="button"
          className="view-tab"
          aria-current={view === 'capture' ? 'page' : undefined}
          onClick={() => onViewChange('capture')}
        >
          <Icon name="camera" />
          <span>Camera</span>
        </button>
        <button
          type="button"
          className="view-tab"
          aria-current={view === 'read' ? 'page' : undefined}
          onClick={() => onViewChange('read')}
        >
          <Icon name="text" />
          <span>Text</span>
          {hasResult && <span className="view-tab__dot" aria-label="(text available)" />}
        </button>
      </nav>

      <button type="button" className="btn btn--icon" onClick={onOpenSettings} aria-haspopup="dialog">
        <Icon name="settings" />
        <span>Display</span>
      </button>
    </header>
  )
}
