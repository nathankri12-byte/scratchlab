/* Transparent 3D overlay for remote Poly Track cars.
   Uses the game's car transform and chase-camera formula; the original game stays untouched. */
(async function(){
  try {
    const THREE = await import("https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js");
    const canvas = document.createElement("canvas");
    canvas.id = "pt-remote-car-layer";
    Object.assign(canvas.style,{position:"fixed",inset:"0",width:"100vw",height:"100vh",pointerEvents:"none",zIndex:"4"});
    document.body.appendChild(canvas);
    const renderer = new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:"low-power"});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
    renderer.setSize(window.innerWidth,window.innerHeight,false);
    renderer.setClearColor(0x000000,0);
    const scene = new THREE.Scene();
    scene.add(new THREE.AmbientLight(0xffffff,1.25));
    const sun = new THREE.DirectionalLight(0xffffff,2.0);sun.position.set(-5,10,7);scene.add(sun);
    const camera = new THREE.PerspectiveCamera(70,window.innerWidth/window.innerHeight,.5,1500);
    const cars = new Map();
    const colors=[0xffbd59,0x78a9ff,0xff6f91,0xb49aff,0x8fe0a1,0xff8e52,0x5eead4];
    function makeCar(color){
      const group=new THREE.Group();
      const bodyMat=new THREE.MeshStandardMaterial({color,roughness:.48,metalness:.12});
      const glassMat=new THREE.MeshStandardMaterial({color:0x172a3a,roughness:.25,metalness:.15});
      const rubber=new THREE.MeshStandardMaterial({color:0x10151b,roughness:.9});
      const body=new THREE.Mesh(new THREE.BoxGeometry(1.5,.48,3.05),bodyMat);body.position.y=.48;group.add(body);
      const cabin=new THREE.Mesh(new THREE.BoxGeometry(1.12,.58,1.42),glassMat);cabin.position.set(0,.94,-.12);group.add(cabin);
      for(const x of [-.79,.79]) for(const z of [-1.02,1.02]){
        const wheel=new THREE.Mesh(new THREE.CylinderGeometry(.34,.34,.22,10),rubber);
        wheel.rotation.z=Math.PI/2;wheel.position.set(x,.31,z);group.add(wheel);
      }
      const nose=new THREE.Mesh(new THREE.BoxGeometry(1.12,.12,.16),new THREE.MeshStandardMaterial({color:0xffffff}));
      nose.position.set(0,.48,1.54);group.add(nose);
      scene.add(group);return group;
    }
    function resize(){renderer.setSize(window.innerWidth,window.innerHeight,false);camera.aspect=window.innerWidth/window.innerHeight;camera.updateProjectionMatrix()}
    window.addEventListener("resize",resize);
    function animate(){
      requestAnimationFrame(animate);
      const local=window.__ptLocalCarState;
      if(local && Number.isFinite(local.x) && Number.isFinite(local.z)){
        const rawQ=new THREE.Quaternion(local.qx,local.qy,local.qz,local.qw);
        const yaw=new THREE.Euler().setFromQuaternion(rawQ,"YXZ").y;
        const q=new THREE.Quaternion().setFromEuler(new THREE.Euler(0,yaw,0));
        const offset=new THREE.Vector3(0,1.1,.4).applyQuaternion(q);
        camera.position.set(local.x,local.y,local.z).add(offset);
        camera.quaternion.copy(q).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0,Math.PI,0)));
        const speed=Math.abs(Number(local.speedKmh)||0);
        camera.fov=70+10*(1-Math.exp(-speed/200));camera.updateProjectionMatrix();
        const players=window.__ptRemotePlayers||[];
        const visible=new Set();
        players.forEach((p,index)=>{
          if(!p.position || p.id===window.__ptPlayerId) return;
          const v=p.position;
          if(![v.x,v.y,v.z,v.qx,v.qy,v.qz,v.qw].every(Number.isFinite)) return;
          visible.add(p.id);
          let car=cars.get(p.id);
          if(!car){car=makeCar(colors[index%colors.length]);cars.set(p.id,car)}
          car.visible=true;car.scale.setScalar(1.55);car.position.lerp(new THREE.Vector3(v.x,v.y,v.z),.32);const remoteQ=new THREE.Quaternion(v.qx,v.qy,v.qz,v.qw);const remoteYaw=new THREE.Euler().setFromQuaternion(remoteQ,"YXZ").y;car.quaternion.slerp(new THREE.Quaternion().setFromEuler(new THREE.Euler(0,remoteYaw,0)),.32);
        });
        for(const [id,car] of cars){if(!visible.has(id))car.visible=false}
        renderer.render(scene,camera);
      } else {
        renderer.clear();
      }
    }
    animate();
    window.__pt3DOverlayReady=true;
  } catch(error) {
    window.__pt3DOverlayError=String(error);
    console.warn("Poly Track remote-car overlay unavailable:",error);
  }
})();