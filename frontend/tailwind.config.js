/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Design token palette
        base: '#0a0f1e',
        surface: '#0f1629',
        card: 'rgba(255,255,255,0.03)',
        // Accent
        indigo: {
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
        },
        // Sidebar kept as custom
        sidebar: '#080d1a',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'gradient-premium': 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%)',
        'gradient-card-hover': 'linear-gradient(145deg, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.06) 100%)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease both',
        'slide-up': 'slideUp 0.4s ease both',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(16px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 10px rgba(99,102,241,0.2)' },
          '50%': { boxShadow: '0 0 30px rgba(99,102,241,0.4)' },
        },
      },
      boxShadow: {
        'glass': '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)',
        'card': '0 4px 24px rgba(0,0,0,0.3)',
        'glow': '0 0 40px rgba(99,102,241,0.25)',
        'glow-sm': '0 0 20px rgba(99,102,241,0.15)',
      },
      borderColor: {
        glass: 'rgba(255,255,255,0.08)',
        'glass-medium': 'rgba(255,255,255,0.12)',
      },
      backdropBlur: {
        xs: '4px',
      },
    },
  },
  plugins: [],
};
