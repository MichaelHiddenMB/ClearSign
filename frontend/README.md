# ClearSign client

React 19 + TypeScript, built with Vite. No UI framework; styling is plain CSS with design tokens in `src/styles/tokens.css`.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server on http://localhost:5173 with `/api` proxied to the FastAPI service |
| `npm run build` | Typecheck and produce a production bundle in `dist/` |
| `npm run preview` | Serve the production bundle locally |
| `npm run lint` | Run oxlint |

Copy `.env.example` to `.env` to change the API target or force sample results.

## Structure

```
src/
  App.tsx                 State for capture → recognise → read, wires the panels together
  components/
    TopBar.tsx            Wordmark, Camera/Text switch (bottom bar on phones), Display button
    Viewfinder.tsx        Live camera preview, capture button, photo-library fallback
    Reader.tsx            Enlarged text surface, size stepper, read-aloud controls, photo zoom
    SettingsPanel.tsx     Colour themes, typeface, spacing, weight, speech rate and voice
    Icon.tsx              Inline SVG icon set
  hooks/
    useCamera.ts          getUserMedia lifecycle and permission states
    useSpeech.ts          Web Speech API: line-by-line utterances with word boundaries
    useSettings.ts        Persisted display settings; syncs app chrome to the reader theme
  lib/
    ocr.ts                API client for POST /api/ocr, with a dev-only sample fallback
    capture.ts            Grabs a JPEG frame from the video element
    settings.ts           Theme, font, and spacing definitions plus defaults and validation
  styles/
    tokens.css            Light and dark chrome palettes, type, control sizes
    base.css              Reset, focus ring, reduced-motion, skip link
    app.css               Component styles
```

## Accessibility notes

- Default reader face is Atkinson Hyperlegible, designed for low-vision readers; Lexend, the system sans, and a serif are also offered.
- Six reader colour themes, including yellow-on-black and black-on-yellow, with the app chrome switching to match.
- Every control is at least 48px tall, has a visible text label or an accessible name, and a high-visibility focus ring.
- Status changes (recognising, results, errors) are announced through live regions.
- The Camera/Text switch sits at the bottom of the screen on phones so it is within thumb reach.
- Space captures a frame while the camera is live.
- Respects `prefers-reduced-motion` and `prefers-contrast: more`.
