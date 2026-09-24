import { defineConfig } from 'vite';

// Relative base so the build works from any folder (web portals host games in subpaths).
export default defineConfig({
  base: './',
  build: { chunkSizeWarningLimit: 1000 },
});
