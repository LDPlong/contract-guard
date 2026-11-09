/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#2F6FED',
          dark: '#1E56C8',
          light: '#EBF1FE',
        },
        risk: {
          high: '#E5484D',
          medium: '#F5A524',
          low: '#30A46C',
        },
        ink: {
          DEFAULT: '#1A1D24',
          soft: '#5A6272',
          faint: '#8A91A0',
        },
      },
      borderRadius: {
        card: '8px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0, 0, 0, .06)',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
}
