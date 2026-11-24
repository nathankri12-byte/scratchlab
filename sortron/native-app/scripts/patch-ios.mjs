import fs from "node:fs";
import path from "node:path";

const plistPath = path.resolve("ios/App/App/Info.plist");
if (!fs.existsSync(plistPath)) {
  throw new Error("iOS-Projekt fehlt. Zuerst npx cap add ios ausführen.");
}
let plist = fs.readFileSync(plistPath, "utf8");
const entries = [
  ["NSBluetoothAlwaysUsageDescription", "Sortron verbindet sich per Bluetooth mit dem Matrix Mini R4."],
  ["NSCameraUsageDescription", "Sortron nutzt die Kamera zur Erkennung von Abfällen."]
];
for (const [key, value] of entries) {
  if (!plist.includes("<key>" + key + "</key>")) {
    plist = plist.replace("</dict>", "  <key>" + key + "</key>\n  <string>" + value + "</string>\n</dict>");
  }
}
fs.writeFileSync(plistPath, plist);
console.log("iOS privacy descriptions added.");
