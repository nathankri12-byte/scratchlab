import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: "src/native-ble.js",
      name: "SortronNativeBLEBundle",
      formats: ["iife"],
      fileName: () => "native-ble.js"
    },
    outDir: "www/js",
    emptyOutDir: false,
    target: "es2020"
  }
});
