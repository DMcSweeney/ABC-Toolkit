/** @type {import('tailwindcss').Config} */

// Token colors are CSS-variable-backed (see src/index.css for the light/dark values) so the
// whole app is theme-reactive from one place. Note: brand/accent shade *numbers* don't mean
// the same literal lightness in both themes (e.g. brand-300 is a pale mint in dark mode but a
// deep emerald in light mode) — they're chosen per-theme so the same class stays legible as
// text/icon color on that theme's background, not just as button fills. surface/ink/line don't
// have this wrinkle since they're never combined with themselves for contrast.
function withOpacity(variableName) {
  return `rgb(var(${variableName}) / <alpha-value>)`
}

export default {
  content: [
    "./index.html",
    "./src/**/*/*.{html,js,vue}",
    "node_modules/flowbite-vue/**/*.{js,jsx,ts,tsx,vue}",
    "node_modules/flowbite/**/*.{js,jsx,ts,tsx}"],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    fontFamily: {
      sans: ['Raleway', 'sans-serif'],
      serif: ['Merriweather', 'serif'],
    },
    extend: {
      colors: {
        surface: {
          header: withOpacity('--color-surface-header'),
          app: withOpacity('--color-surface-app'),
          card: withOpacity('--color-surface-card'),
          raised: withOpacity('--color-surface-raised'),
        },
        ink: {
          primary: withOpacity('--color-ink-primary'),
          secondary: withOpacity('--color-ink-secondary'),
          muted: withOpacity('--color-ink-muted'),
        },
        line: {
          subtle: withOpacity('--color-line-subtle'),
          default: withOpacity('--color-line-default'),
        },
        brand: {
          50: withOpacity('--color-brand-50'),
          300: withOpacity('--color-brand-300'),
          400: withOpacity('--color-brand-400'),
          500: withOpacity('--color-brand-500'),
          600: withOpacity('--color-brand-600'),
          700: withOpacity('--color-brand-700'),
        },
        accent: {
          300: withOpacity('--color-accent-300'),
          400: withOpacity('--color-accent-400'),
          500: withOpacity('--color-accent-500'),
        },
      },
    },
  },
  plugins: [
    require('flowbite/plugin')({
      tables: false,
    }),
    require('@tailwindcss/forms'),
  ],
}

