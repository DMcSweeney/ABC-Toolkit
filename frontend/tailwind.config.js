/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*/*.{html,js,vue}",
    "node_modules/flowbite-vue/**/*.{js,jsx,ts,tsx,vue}",
    "node_modules/flowbite/**/*.{js,jsx,ts,tsx}"],
  theme: {
    fontFamily: {
      sans: ['Raleway', 'sans-serif'],
      serif: ['Merriweather', 'serif'],
    },
    extend: {
      colors: {
        surface: {
          header: '#020617',
          app: '#0f172a',
          card: '#1e293b',
          raised: '#334155',
        },
        ink: {
          primary: '#f1f5f9',
          secondary: '#cbd5e1',
          muted: '#64748b',
        },
        line: {
          subtle: '#334155',
          default: '#475569',
        },
        brand: {
          50: '#eef2ff',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
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

