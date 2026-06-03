/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Dark editor palette — inspired by Premiere Pro / DaVinci Resolve
        editor: {
          bg:       '#141414',
          surface:  '#1c1c1c',
          panel:    '#222222',
          border:   '#2e2e2e',
          hover:    '#292929',
          active:   '#2e2e2e',
          muted:    '#1a1a1a',
        },
        accent: {
          DEFAULT: '#4f8ef7',
          hover:   '#6ba3ff',
          muted:   '#172444',
          glow:    'rgba(79,142,247,0.25)',
        },
        success: {
          DEFAULT: '#22c55e',
          muted:   '#0f2a1a',
          hover:   '#34d473',
        },
        warning: {
          DEFAULT: '#f59e0b',
          muted:   '#2d1f04',
          hover:   '#fbbf24',
        },
        danger: {
          DEFAULT: '#ef4444',
          muted:   '#2d0f0f',
          hover:   '#f87171',
        },
        score: {
          high:   '#22c55e',
          medium: '#f59e0b',
          low:    '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
        '3xs': ['0.5rem',   { lineHeight: '0.75rem'  }],
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
      },
      animation: {
        'pulse-slow':  'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up':    'slideUp 0.2s ease-out',
        'slide-down':  'slideDown 0.2s ease-out',
        'fade-in':     'fadeIn 0.15s ease-out',
        'scale-in':    'scaleIn 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)',
        'shimmer':     'shimmer 1.8s ease-in-out infinite',
      },
      keyframes: {
        slideUp: {
          '0%':   { transform: 'translateY(8px)',  opacity: 0 },
          '100%': { transform: 'translateY(0)',    opacity: 1 },
        },
        slideDown: {
          '0%':   { transform: 'translateY(-8px)', opacity: 0 },
          '100%': { transform: 'translateY(0)',    opacity: 1 },
        },
        fadeIn: {
          '0%':   { opacity: 0 },
          '100%': { opacity: 1 },
        },
        scaleIn: {
          '0%':   { transform: 'scale(0.93)', opacity: 0 },
          '100%': { transform: 'scale(1)',    opacity: 1 },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0'  },
        },
      },
      boxShadow: {
        'accent-sm': '0 0 8px rgba(79,142,247,0.3)',
        'accent-md': '0 0 16px rgba(79,142,247,0.25)',
        'success-sm':'0 0 8px rgba(34,197,94,0.3)',
        'inner-glow': 'inset 0 1px 0 rgba(255,255,255,0.06)',
      },
      backgroundImage: {
        'grid-pattern': 'linear-gradient(rgba(79,142,247,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(79,142,247,0.04) 1px, transparent 1px)',
      },
      backgroundSize: {
        'grid': '20px 20px',
      },
    },
  },
  plugins: [],
}
