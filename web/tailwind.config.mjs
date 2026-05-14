// Tailwind 4 prefers CSS-first config via the @theme directive in
// src/styles/global.css; this file is kept for any future tooling that
// expects a JS config to exist. All brand tokens live in tokens.css.
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx}'],
};
