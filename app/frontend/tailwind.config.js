/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'bridge-purple': '#8B5CF6',
        'bridge-blue': '#3B82F6',
        'dark-bg': '#0F172A',
        'dark-card': '#1E293B',
      },
    },
  },
  plugins: [],
}