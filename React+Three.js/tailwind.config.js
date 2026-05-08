/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Industrial precision palette
        industrial: {
          50: '#f0f4f8',
          100: '#d9e2ec',
          200: '#bcccdc',
          300: '#9fb3c8',
          400: '#829ab1',
          500: '#627d98',
          600: '#486581',
          700: '#334e68',
          800: '#243b53',
          900: '#102a43',
          950: '#0a1929',
        },
        // Neon technical accents
        neon: {
          cyan: '#00d9ff',
          blue: '#0080ff',
          purple: '#8b5cf6',
          green: '#10b981',
          amber: '#f59e0b',
          red: '#ef4444',
        },
        // Deviation heatmap
        deviation: {
          cold: '#3b82f6',    // blue (inside CAD)
          neutral: '#f3f4f6', // white (on surface)
          warm: '#ef4444',    // red (outside CAD)
        },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
        display: ['Orbitron', 'sans-serif'],
      },
      animation: {
        'scan-line': 'scan-line 2s linear infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'slide-up': 'slide-up 0.3s ease-out',
      },
      keyframes: {
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.4', filter: 'blur(8px)' },
          '50%': { opacity: '0.8', filter: 'blur(12px)' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      boxShadow: {
        'neon-sm': '0 0 10px rgba(0, 217, 255, 0.3)',
        'neon': '0 0 20px rgba(0, 217, 255, 0.5)',
        'neon-lg': '0 0 30px rgba(0, 217, 255, 0.7)',
      },
    },
  },
  plugins: [],
}
