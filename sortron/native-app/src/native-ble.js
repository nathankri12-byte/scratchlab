import { Capacitor } from "@capacitor/core";
import { BleClient } from "@capacitor-community/bluetooth-le";

const SERVICE = "19b10000-e8f2-537e-4f6c-d104768a1214";
const CHARACTERISTIC = "19b10001-e8f2-537e-4f6c-d104768a1214";
const DEVICE_NAME = "MiniR4 Sorter";

if (Capacitor.isNativePlatform()) {
  let device = null;
  let connected = false;
  let callbacks = {};

  const api = {
    async connect(nextCallbacks = {}) {
      callbacks = nextCallbacks;
      callbacks.onStatus?.("Bluetooth wird initialisiert …", "wait");
      await BleClient.initialize();
      await BleClient.setDisplayStrings({
        scanning: "Sortron sucht den Mini R4 …",
        cancel: "Abbrechen",
        availableDevices: "Verfügbare Geräte",
        noDeviceFound: "Kein Mini R4 gefunden"
      });
      device = await BleClient.requestDevice({
        name: DEVICE_NAME,
        services: [SERVICE]
      });
      callbacks.onStatus?.("Verbindung wird aufgebaut …", "wait");
      await BleClient.connect(
        device.deviceId,
        () => {
          connected = false;
          callbacks.onStatus?.("Verbindung getrennt", "");
          callbacks.onDisconnect?.();
        },
        { services: [SERVICE] }
      );
      connected = true;
      callbacks.onStatus?.("Verbunden", "ok");
      callbacks.onLog?.("Bluetooth verbunden: " + (device.name || DEVICE_NAME));
      return device;
    },

    async send(command) {
      const value = String(command);
      if (!["0", "1", "2", "3", "4"].includes(value)) {
        throw new Error("Unbekannter Sortron-Befehl: " + value);
      }
      if (!device || !connected) throw new Error("MiniR4 Sorter ist nicht verbunden.");
      const bytes = new Uint8Array([value.charCodeAt(0)]);
      await BleClient.write(
        device.deviceId,
        SERVICE,
        CHARACTERISTIC,
        new DataView(bytes.buffer)
      );
    },

    async disconnect() {
      if (device && connected) {
        await BleClient.disconnect(device.deviceId);
      }
      connected = false;
      device = null;
    },

    isConnected() {
      return connected;
    }
  };

  window.SortronNativeBLE = api;
}
