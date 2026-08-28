import * as THREE from "three";

function starSprite(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return new THREE.Texture();
  }
  const glow = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  glow.addColorStop(0, "rgba(255,255,255,1)");
  glow.addColorStop(0.08, "rgba(255,255,255,0.95)");
  glow.addColorStop(0.22, "rgba(255,255,255,0.28)");
  glow.addColorStop(0.55, "rgba(255,255,255,0.04)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function scatterSphere(count: number, radius: number): Float32Array {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    const depth = radius * (0.25 + Math.random() * 0.75);
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = depth * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = depth * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = depth * Math.cos(phi);
  }
  return positions;
}

function scatterDisk(count: number, radius: number, thickness: number): Float32Array {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    const depth = radius * Math.sqrt(Math.random());
    const theta = Math.random() * Math.PI * 2;
    positions[i * 3] = depth * Math.cos(theta);
    positions[i * 3 + 1] = (Math.random() - 0.5) * thickness;
    positions[i * 3 + 2] = depth * Math.sin(theta);
  }
  return positions;
}

function field(
  positions: Float32Array,
  size: number,
  color: THREE.ColorRepresentation,
  texture: THREE.Texture,
): THREE.Points {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    size,
    map: texture,
    color,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
    opacity: 0.95,
  });
  return new THREE.Points(geometry, material);
}

export function startUniverse(canvas: HTMLCanvasElement): void {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x050403, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 400);
  camera.position.set(0, 0, 8);

  const sprite = starSprite();
  const far = field(scatterSphere(12000, 170), 0.38, 0xfafaf9, sprite);
  const mid = field(scatterSphere(3800, 110), 0.62, 0xe7e5e4, sprite);
  const band = field(scatterDisk(7000, 130, 18), 0.5, 0xd6d3d1, sprite);
  const near = field(scatterSphere(420, 52), 1.05, 0xd6ff9a, sprite);
  const dust = field(scatterDisk(80, 100, 12), 2.4, 0x292524, sprite);
  band.rotation.x = 0.55;
  band.rotation.z = 0.22;
  dust.rotation.x = 0.55;
  dust.rotation.z = 0.22;
  const universe = new THREE.Group();
  universe.add(far, mid, band, near, dust);
  scene.add(universe);

  const pointer = { x: 0, y: 0 };
  const onPointer = (event: PointerEvent) => {
    pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
    pointer.y = (event.clientY / window.innerHeight) * 2 - 1;
  };
  window.addEventListener("pointermove", onPointer, { passive: true });

  const resize = () => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  window.addEventListener("resize", resize);
  resize();

  let frame = 0;
  const tick = (time: number) => {
    frame = requestAnimationFrame(tick);
    const t = time * 0.0002;
    universe.rotation.y = t;
    universe.rotation.x = Math.sin(t * 0.45) * 0.12;
    universe.rotation.z = Math.cos(t * 0.2) * 0.03;
    const nearMat = near.material as THREE.PointsMaterial;
    nearMat.opacity = 0.72 + Math.sin(time * 0.0016) * 0.22;
    camera.position.x += (pointer.x * 1.4 - camera.position.x) * 0.02;
    camera.position.y += (-pointer.y * 0.9 - camera.position.y) * 0.02;
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
  };

  renderer.render(scene, camera);
  if (!reduceMotion) {
    frame = requestAnimationFrame(tick);
  }

  if (import.meta.hot) {
    import.meta.hot.dispose(() => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("resize", resize);
      renderer.dispose();
    });
  }
}
