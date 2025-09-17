import fs from 'fs';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';


// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
     allowedHosts: true,
     https: {
      key: fs.readFileSync('/ssl/cert.key'),
      cert: fs.readFileSync('/ssl/cert.crt'),
      //passphrase: 'donal'
     }
  }
})
