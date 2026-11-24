import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");
const sortronRoot = path.resolve(appRoot, "..");
const webDir = path.join(appRoot, "www");

fs.rmSync(webDir, { recursive: true, force: true });
fs.mkdirSync(webDir, { recursive: true });

// Copy the website into the app bundle, excluding this native-app folder.
// Copying the parent directory in one operation is invalid because www lives
// inside native-app and would otherwise recursively copy itself.
for (const entry of fs.readdirSync(sortronRoot, { withFileTypes: true })) {
  if (entry.name === "native-app") continue;
  const source = path.join(sortronRoot, entry.name);
  const destination = path.join(webDir, entry.name);
  fs.cpSync(source, destination, { recursive: true });
}

const softwarePath = path.join(webDir, "software.html");
let html = fs.readFileSync(softwarePath, "utf8");
const marker = '<script src="js/sortron-ble.js"></script>';
if (!html.includes('src="js/native-ble.js"')) {
  if (!html.includes(marker)) {
    throw new Error("BLE script marker not found in software.html");
  }
  html = html.replace(marker, '<script src="js/native-ble.js"></script>\\n' + marker);
}
fs.writeFileSync(softwarePath, html);

await build({ configFile: path.join(appRoot, "vite.config.mjs") });
console.log("Sortron web assets and native BLE bridge built into www/.");
