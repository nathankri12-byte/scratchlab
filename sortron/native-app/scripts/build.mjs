import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");
const sortronRoot = path.resolve(appRoot, "..");
const webDir = path.join(appRoot, "www");

fs.rmSync(webDir, { recursive: true, force: true });
fs.cpSync(sortronRoot, webDir, {
  recursive: true,
  filter(source) {
    const relative = path.relative(sortronRoot, source);
    return relative === "" || !relative.split(path.sep).includes("native-app");
  }
});

const softwarePath = path.join(webDir, "software.html");
let html = fs.readFileSync(softwarePath, "utf8");
const marker = '<script src="js/sortron-ble.js"></script>';
if (!html.includes('src="js/native-ble.js"')) {
  html = html.replace(marker, '<script src="js/native-ble.js"></script>\n' + marker);
}
fs.writeFileSync(softwarePath, html);

await build({ configFile: path.join(appRoot, "vite.config.mjs") });
console.log("Sortron web assets and native BLE bridge built into www/.");
