/*
  SORTRON – Mini R4 BLE + M1 Motor Test Firmware
  Separate test firmware. Does NOT modify the existing V6 servo sketch.

  BLE protocol (same identifiers as website):
    Device:        MiniR4 Sorter
    Service UUID:  19b10000-e8f2-537e-4f6c-d104768a1214
    Char UUID:     19b10001-e8f2-537e-4f6c-d104768a1214

  Website sends one ASCII byte:
    '0' = stop / idle
    '1' = Papier
    '2' = Plastik
    '3' = Bio
    '4' = Restmuell

  IMPORTANT:
  For this first hardware test, commands 1–4 all run M1 at +50 power
  for 500 ms, then stop. Nathan measured this as approximately half a
  motor rotation. This verifies BLE reception + M1 control only; it is
  NOT yet the final four-position sorting motion.
*/

#include <ArduinoBLE.h>
#include <MatrixMiniR4.h>

const char* DEVICE_NAME = "MiniR4 Sorter";

BLEService sortronService("19b10000-e8f2-537e-4f6c-d104768a1214");
BLEByteCharacteristic commandCharacteristic(
  "19b10001-e8f2-537e-4f6c-d104768a1214",
  BLERead | BLEWrite | BLEWriteWithoutResponse
);

const int MOTOR_POWER = 50;
const unsigned long MOTOR_RUN_MS = 500;

bool motorRunning = false;
unsigned long motorStopAt = 0;
byte lastCommand = 0;

void stopMotor() {
  MiniR4.M1.setPower(0);
  motorRunning = false;
}

void runMotorTest(byte command) {
  // Stop any previous movement before starting a new test movement.
  stopMotor();

  if (command < '1' || command > '4') {
    return;
  }

  Serial.print("Sortron command received: ");
  Serial.write(command);
  Serial.println();

  MiniR4.M1.setPower(MOTOR_POWER);
  motorRunning = true;
  motorStopAt = millis() + MOTOR_RUN_MS;
}

void setup() {
  Serial.begin(115200);
  MiniR4.begin();

  stopMotor();

  if (!BLE.begin()) {
    Serial.println("ERROR: BLE could not be initialized.");
    while (true) {
      stopMotor();
      delay(100);
    }
  }

  BLE.setLocalName(DEVICE_NAME);
  BLE.setDeviceName(DEVICE_NAME);
  BLE.setAdvertisedService(sortronService);

  sortronService.addCharacteristic(commandCharacteristic);
  BLE.addService(sortronService);

  commandCharacteristic.writeValue((byte)'0');
  BLE.advertise();

  Serial.println("SORTRON BLE ready.");
  Serial.print("Advertising as: ");
  Serial.println(DEVICE_NAME);
}

void loop() {
  BLE.poll();

  if (commandCharacteristic.written()) {
    byte command = commandCharacteristic.value();

    // Ignore repeated writes of the same command until a new value arrives.
    if (command != lastCommand || command == '0') {
      lastCommand = command;

      if (command == '0') {
        stopMotor();
        Serial.println("Stop command received.");
      } else if (command >= '1' && command <= '4') {
        runMotorTest(command);
      } else {
        Serial.print("Unknown command byte: ");
        Serial.println(command);
      }
    }
  }

  if (motorRunning && (long)(millis() - motorStopAt) >= 0) {
    stopMotor();
    Serial.println("M1 test movement finished.");
  }
}
