/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        // 纸感底色：暖白，不用纯白，长时间阅读更舒服
        paper: {
          DEFAULT: '#FBFAF7',
          deep: '#F4F2EB',
          sunk: '#EFEDE5',
        },
        // 墨色三层，替代纯黑
        ink: {
          DEFAULT: '#15171C',
          soft: '#4E545E',
          faint: '#8A8F98',
        },
        line: {
          DEFAULT: '#E5E2DA',
          strong: '#D2CEC3',
        },
        // 藏青：法徽/印章的沉稳蓝，替代亮蓝
        accent: {
          DEFAULT: '#1B3A6B',
          deep: '#12294D',
          soft: '#5A7099',
          wash: '#EEF1F6',
        },
        risk: {
          high: '#B3261E',
          medium: '#A96A00',
          low: '#2F6B4F',
        },
      },
      fontFamily: {
        sans: [
          '"PingFang SC"',
          '"Microsoft YaHei"',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'sans-serif',
        ],
        serif: [
          '"Source Han Serif SC"',
          '"Noto Serif SC"',
          '"Songti SC"',
          'SimSun',
          'Georgia',
          'serif',
        ],
      },
      borderRadius: {
        // 锐角更接近印刷品，圆角反而显廉价
        card: '2px',
        pill: '999px',
      },
      boxShadow: {
        page: '0 1px 2px rgba(21,23,28,.05), 0 12px 28px -18px rgba(21,23,28,.18)',
        lift: '0 2px 4px rgba(21,23,28,.06), 0 16px 32px -20px rgba(21,23,28,.22)',
      },
      letterSpacing: {
        tightest: '-0.03em',
        label: '0.18em',
      },
      transitionTimingFunction: {
        calm: 'cubic-bezier(.22,.61,.36,1)',
      },
      keyframes: {
        rise: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseRing: {
          '0%,100%': { opacity: '1' },
          '50%': { opacity: '.35' },
        },
      },
      animation: {
        rise: 'rise .34s cubic-bezier(.22,.61,.36,1) both',
        pulseRing: 'pulseRing 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
