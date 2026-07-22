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
          header: '#0a0e14',
          app: '#0d1117',
          card: '#161b22',
          raised: '#21262d',
        },
        ink: {
          primary: '#e6edf3',
          secondary: '#adbac7',
          muted: '#6e7681',
        },
        line: {
          subtle: '#30363d',
          default: '#3d444d',
        },
        brand: {
          50: '#ecfdf5',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
        },
        accent: {
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
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

