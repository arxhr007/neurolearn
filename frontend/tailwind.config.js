/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        greige: { bg: '#efedea', panel: '#f9f8f6', border: '#dcd8d0', accent: '#e4e2de' },
        ink: '#2c2b29',
        muted: '#62605a',
        sage: { DEFAULT: '#6b8378', soft: '#e3e7e2', dark: '#4e6359' },
        clay: { DEFAULT: '#9a6e66', soft: '#efe3e0' },
        sidebar: '#2a2f35',
      },
      fontFamily: { sans: ['"Space Grotesk"', 'Segoe UI', 'sans-serif'] },
      boxShadow: {
        card: '0 8px 20px rgba(60,55,50,0.06)',
        lift: '0 14px 30px rgba(60,55,50,0.11)',
        glass: '0 4px 24px rgba(60,55,50,0.09), inset 0 1px 0 rgba(255,255,255,0.6)',
      },
      borderRadius: { '2xl': '1rem', '3xl': '1.5rem' },
    },
  },
  plugins: [],
};
