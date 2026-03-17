/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Medical teal — primary brand
        brand: {
          50:  '#effefb',
          100: '#c8fff4',
          200: '#91feea',
          300: '#53f5db',
          400: '#20e0c7',
          500: '#09c4ae',
          600: '#049e8f',
          700: '#087e74',
          800: '#0c645e',
          900: '#0f524e',
          950: '#013331',
        },
        // Sidebar / authority dark
        sidebar: {
          DEFAULT: '#0f172a',
          hover:   '#1e293b',
          active:  '#1a2744',
          border:  '#1e293b',
        },
        // Surface tones
        surface: {
          DEFAULT: '#f8fafc',
          card:    '#ffffff',
          raised:  '#ffffff',
          muted:   '#f1f5f9',
        },
        // Risk / compliance
        risk: {
          low:      '#10b981',
          moderate: '#f59e0b',
          high:     '#f97316',
          critical: '#ef4444',
        },
        state: {
          clean:        '#10b981',
          potential:    '#f59e0b',
          contaminated: '#f97316',
          dirty:        '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'card':   '0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-hover': '0 4px 12px 0 rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.04)',
        'sidebar': '4px 0 24px 0 rgb(0 0 0 / 0.12)',
        'glow-brand': '0 0 20px rgb(9 196 174 / 0.15)',
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #087e74 0%, #09c4ae 100%)',
        'gradient-dark':  'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'float-delayed': 'float 8s ease-in-out 2s infinite',
        'float-slow': 'float 10s ease-in-out 4s infinite',
        'fade-in-up': 'fadeInUp 0.6s ease-out both',
        'fade-in-up-delay-1': 'fadeInUp 0.6s ease-out 0.1s both',
        'fade-in-up-delay-2': 'fadeInUp 0.6s ease-out 0.2s both',
        'fade-in-up-delay-3': 'fadeInUp 0.6s ease-out 0.3s both',
        'shimmer': 'shimmer 2s linear infinite',
        'glow-pulse': 'glowPulse 3s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 20px rgb(9 196 174 / 0.15)' },
          '50%': { boxShadow: '0 0 30px rgb(9 196 174 / 0.35)' },
        },
      },
    },
  },
  plugins: [],
}
