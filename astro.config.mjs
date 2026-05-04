import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://profwashingtonaraujo.github.io',
  base: '/ibrcanaa',
  vite: {
    plugins: [tailwindcss()],
  },
});
