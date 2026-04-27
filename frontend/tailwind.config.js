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
          DEFAULT: '#ff5a3c',
          50: '#fff1ed',
          100: '#ffe1d6',
          200: '#ffc7b7',
          300: '#ff9f7c',
          400: '#ff7c59',
          500: '#ff5a3c',
          600: '#f04a2a',
          700: '#cf391a',
          800: '#a62c13',
          900: '#7d1f0d',
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
          DEFAULT: '#fff7f0',
          card: '#fffdf9',
          hover: '#fff3e6',
          border: '#f0ddd1',
          'border-light': '#f8ece4',
        },
        content: {
          DEFAULT: '#2f241f',
          secondary: '#7b675b',
          tertiary: '#b49a8c',
          inverse: '#fffdf8',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'sans-serif'],
      },
      boxShadow: {
        xs: '0 4px 12px rgba(111, 57, 35, 0.06)',
        card: '0 18px 40px -28px rgba(166, 74, 33, 0.28)',
        md: '0 24px 60px -34px rgba(166, 74, 33, 0.32)',
        lg: '0 32px 80px -36px rgba(120, 53, 25, 0.35)',
        xl: '0 40px 120px -44px rgba(120, 53, 25, 0.42)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.35s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'float-soft': 'floatSoft 6s ease-in-out infinite',
      },
      backgroundImage: {
        'fanqie-hero': 'linear-gradient(135deg, rgba(255,113,72,1) 0%, rgba(255,153,89,1) 55%, rgba(255,214,166,0.95) 100%)',
        'fanqie-panel': 'linear-gradient(180deg, rgba(255,253,249,0.98) 0%, rgba(255,245,236,0.95) 100%)',
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
