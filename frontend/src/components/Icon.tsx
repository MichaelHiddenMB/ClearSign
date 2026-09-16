export type IconName =
  | 'camera'
  | 'upload'
  | 'settings'
  | 'play'
  | 'pause'
  | 'stop'
  | 'plus'
  | 'minus'
  | 'close'
  | 'retake'
  | 'text'
  | 'image'
  | 'zoom-in'
  | 'zoom-out'

const PATHS: Record<IconName, string> = {
  camera: 'M4 8h3l2-3h6l2 3h3v11H4z M12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
  upload: 'M12 16V4 M7 9l5-5 5 5 M4 20h16',
  settings: 'M4 7h16 M4 12h16 M4 17h16 M9 5v4 M15 10v4 M7 15v4',
  play: 'M7 4l13 8-13 8z',
  pause: 'M6 4h4v16H6z M14 4h4v16h-4z',
  stop: 'M5 5h14v14H5z',
  plus: 'M12 5v14 M5 12h14',
  minus: 'M5 12h14',
  close: 'M6 6l12 12 M18 6L6 18',
  retake: 'M4 12a8 8 0 1 1 2.3 5.7 M4 20v-6h6',
  text: 'M5 6h14 M12 6v13 M8 19h8',
  image: 'M4 5h16v14H4z M4 15l5-5 4 4 3-3 4 4 M15 9.5a1 1 0 1 0 0-.1',
  'zoom-in': 'M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12z M14.5 14.5L20 20 M10 7v6 M7 10h6',
  'zoom-out': 'M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12z M14.5 14.5L20 20 M7 10h6',
}

interface IconProps {
  name: IconName
  size?: number
}

export function Icon({ name, size = 24 }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={name === 'play' || name === 'stop' || name === 'pause' ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
