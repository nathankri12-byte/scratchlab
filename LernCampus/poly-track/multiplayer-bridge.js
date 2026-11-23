/* Poly Track multiplayer telemetry bridge.
   Reads the simulation worker's public UpdateResult messages without changing game logic. */
(function(){
  if (!window.Worker || window.__ptWorkerBridgeInstalled) return;
  window.__ptWorkerBridgeInstalled = true;
  const NativeWorker = window.Worker;
  function PolyTrackWorker(...args) {
    const worker = Reflect.construct(NativeWorker, args, new.target || NativeWorker);
    if (String(args[0] || "").includes("simulation_worker.bundle.js")) {
      worker.addEventListener("message", event => {
        const data = event.data;
        if (!data || data.messageType !== 10 || !Array.isArray(data.carStates)) return;
        const car = data.carStates.find(item =>
          item && item.hasStarted && item.position && item.quaternion
        );
        if (!car) return;
        window.__ptLocalCarState = {
          x: car.position.x, y: car.position.y, z: car.position.z,
          qx: car.quaternion.x, qy: car.quaternion.y,
          qz: car.quaternion.z, qw: car.quaternion.w,
          speedKmh: car.speedKmh, frames: car.frames,
          controls: car.controls || {}
        };
      });
    }
    return worker;
  }
  PolyTrackWorker.prototype = NativeWorker.prototype;
  Object.setPrototypeOf(PolyTrackWorker, NativeWorker);
  window.Worker = PolyTrackWorker;
})();