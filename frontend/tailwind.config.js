/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    borderRadius: {
      none: '0px',
      sm: '0px',
      DEFAULT: '0px',
      md: '0px',
      lg: '0px',
      xl: '0px',
      '2xl': '0px',
      '3xl': '0px',
      full: '0px',
      btn: '0px',
      card: '0px',
      modal: '0px',
      pill: '0px',
    },
    extend: {
      colors: {
        brand: {
          DEFAULT: '#007aff',
          50: '#f0f6ff',
          100: '#dcebff',
          200: '#b9d7ff',
          300: '#8ec3ff',
          400: '#3a95ff',
          500: '#007aff',
          600: '#0070eb',
          700: '#005ecc',
          800: '#004ba3',
          900: '#003a7a',
        },
        gold: {
          DEFAULT: '#f2b35d',
          50: '#fff7e8',
          100: '#ffedc7',
          200: '#ffd891',
          300: '#f2b35d',
          400: '#dd9137',
          500: '#bb7123',
        },
        sidebar: {
          DEFAULT: '#311713',
          hover: '#47231d',
          active: '#5b2b23',
          border: '#5d3229',
          text: '#f0d7c8',
          'text-active': '#fffdf8',
        },
        surface: {
          DEFAULT: '#f6f9fd',
          card: '#ffffff',
          hover: '#eef4fc',
          border: '#d9e4f3',
          'border-light': '#e8eff8',
        },
        content: {
          DEFAULT: '#0b1a33',
          secondary: '#5f7090',
          tertiary: '#93a4be',
          inverse: '#ffffff',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'sans-serif'],
      },
      boxShadow: {
        xs: '0 1px 2px rgba(15, 43, 96, 0.04), 0 4px 12px rgba(15, 43, 96, 0.04)',
        card: '0 18px 40px -28px rgba(15, 43, 96, 0.28)',
        md: '0 24px 60px -34px rgba(15, 43, 96, 0.32)',
        lg: '0 32px 80px -36px rgba(15, 43, 96, 0.35)',
        xl: '0 40px 120px -44px rgba(15, 43, 96, 0.42)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.35s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'float-soft': 'floatSoft 6s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        floatSoft: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
}
