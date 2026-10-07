/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#d9e5ff',
          200: '#bcd1ff',
          300: '#8eb3ff',
          400: '#598bff',
          500: '#3366ff',
          600: '#1f47f5',
          700: '#1a35e1',
          800: '#1c2eb6',
          900: '#1d2e8f',
        },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f7f8fa',
          border: '#e5e7eb',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'Segoe UI',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(16 24 40 / 0.05)',
        raised: '0 4px 12px -2px rgb(16 24 40 / 0.08)',
      },
    },
  },
  plugins: [],
};
