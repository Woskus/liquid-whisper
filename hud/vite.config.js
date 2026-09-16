import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base './' — bundle ładowany przez pywebview z pliku (file://)
export default defineConfig({
  base: './',
  plugins: [react()],
})
