/* Sortron BLE bridge – getrennt von KI/Kamera und Arduino-Firmware.
 * Protokoll V6: ASCII-Bytes '0' bis '4' über BLEByteCharacteristic.
 */
(() => {
  'use strict';
  const SERVICE = '19b10000-e8f2-537e-4f6c-d104768a1214';
  const CHARACTERISTIC = '19b10001-e8f2-537e-4f6c-d104768a1214';
  const DEVICE_NAME = 'MiniR4 Sorter';
  let device = null;
  let characteristic = null;
  let disconnectHandler = null;

  function isConnected() {
    return !!(device && device.gatt && device.gatt.connected && characteristic);
  }

  async function connect(callbacks = {}) {
    if (!navigator.bluetooth) {
      throw new Error('Dieser Browser unterstützt Web Bluetooth nicht. Die Sortron-BLE-Verbindung benötigt einen Web-Bluetooth-fähigen Browser.');
    }
    if (isConnected()) return device;
    callbacks.onStatus?.('Bluetooth-Geräte werden gesucht …', 'wait');
    device = await navigator.bluetooth.requestDevice({
      filters: [{ name: DEVICE_NAME }],
      optionalServices: [SERVICE]
    });
    disconnectHandler = () => {
      characteristic = null;
      callbacks.onStatus?.('Verbindung getrennt', '');
      callbacks.onDisconnect?.();
    };
    device.addEventListener('gattserverdisconnected', disconnectHandler);
    const server = await device.gatt.connect();
    const service = await server.getPrimaryService(SERVICE);
    characteristic = await service.getCharacteristic(CHARACTERISTIC);
    if (!characteristic.properties.write && !characteristic.properties.writeWithoutResponse) {
      throw new Error('Die Sortron-BLE-Characteristic erlaubt kein Schreiben.');
    }
    callbacks.onStatus?.('Verbunden', 'ok');
    callbacks.onLog?.('Bluetooth verbunden: ' + (device.name || DEVICE_NAME));
    return device;
  }

  async function send(command) {
    const allowed = ['0', '1', '2', '3', '4'];
    const value = String(command);
    if (!allowed.includes(value)) throw new Error('Unbekannter Sortron-Befehl: ' + value);
    if (!isConnected()) throw new Error('MiniR4 Sorter ist nicht verbunden.');
    // V6 erwartet ein einzelnes ASCII-Byte, z. B. '1', nicht die Zahl 1 als Binärwert.
    const bytes = new TextEncoder().encode(value);
    if (characteristic.writeValueWithResponse) {
      await characteristic.writeValueWithResponse(bytes);
    } else if (characteristic.writeValueWithoutResponse && characteristic.properties.writeWithoutResponse && !characteristic.properties.write) {
      await characteristic.writeValueWithoutResponse(bytes);
    } else {
      await characteristic.writeValue(bytes);
    }
  }

  function disconnect() {
    if (device?.gatt?.connected) device.gatt.disconnect();
    characteristic = null;
  }

  window.SortronBLE = { connect, send, disconnect, isConnected };
})();