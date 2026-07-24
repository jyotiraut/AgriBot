import { useUi } from './ui'

// Hex mirrors of the CSS custom properties in index.css — Recharts renders
// SVG fill/stroke attributes directly, so we keep literal hex here rather
// than depending on var() resolution inside SVG. Two sets so chart ink/grid
// stay legible in dark mode too (unlike CSS, SVG attrs don't inherit the
// `.dark` custom-property overrides).
const LIGHT = {
  moss500: '#5c7a3d',
  moss600: '#46602e',
  moss100: '#d9e0c5',
  terracotta500: '#b6572e',
  terracotta400: '#c96a3f',
  good: '#2f7a2f',
  critical: '#b0392f',
  ink: '#201d16',
  inkSoft: '#55503f',
  inkMuted: '#8b8571',
  hairline: '#ddd6c4',
  surface: '#fffdf8',
}

const DARK = {
  moss500: '#92b86c',
  moss600: '#a9cf85',
  moss100: '#313f22',
  terracotta500: '#e2916a',
  terracotta400: '#d98455',
  good: '#5fbf5f',
  critical: '#e2685c',
  ink: '#f3efe2',
  inkSoft: '#c9c2ab',
  inkMuted: '#8b8571',
  hairline: '#34321f',
  surface: '#201e15',
}

export const CHART = LIGHT

/** Use inside chart components so axis/grid/tooltip colors follow the toggle. */
export function useChartTokens() {
  const theme = useUi((s) => s.theme)
  return theme === 'dark' ? DARK : LIGHT
}
