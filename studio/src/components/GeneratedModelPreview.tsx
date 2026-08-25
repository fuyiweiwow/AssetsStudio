import { Suspense, useEffect, useMemo } from "react";
import { OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

interface GeneratedModelPreviewProps {
  modelUrl: string;
  animationLabel?: string;
}

function GeneratedShape({ modelUrl }: GeneratedModelPreviewProps) {
  const { scene, animations } = useGLTF(modelUrl);
  const fitted = useMemo(() => {
    const object = clone(scene);
    object.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      child.castShadow = true;
      child.receiveShadow = true;
      child.material = new THREE.MeshStandardMaterial({
        color: "#b9c7d5",
        roughness: 0.76,
        metalness: 0,
      });
    });
    const bounds = new THREE.Box3().setFromObject(object);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = 2.45 / Math.max(size.x, size.y, size.z, 0.001);
    object.scale.setScalar(scale);
    object.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
    return object;
  }, [scene]);
  const { actions, names } = useAnimations(animations, fitted);

  useEffect(() => {
    const action = names[0] ? actions[names[0]] : undefined;
    action?.reset().fadeIn(0.15).play();
    return () => {
      action?.fadeOut(0.1);
      action?.stop();
    };
  }, [actions, names]);

  return <primitive object={fitted} />;
}

export function GeneratedModelPreview({ modelUrl, animationLabel }: GeneratedModelPreviewProps) {
  return (
    <div className="generated-model-preview" aria-label="本地 3D 候选交互预览">
      <Canvas camera={{ position: [0, 0.15, 3.8], fov: 32 }} shadows>
        <color attach="background" args={["#111722"]} />
        <ambientLight intensity={1.7} />
        <directionalLight position={[3, 4, 4]} intensity={3.2} castShadow />
        <directionalLight position={[-3, 1, -2]} intensity={1.5} />
        <Suspense fallback={null}>
          <GeneratedShape modelUrl={modelUrl} />
        </Suspense>
        <OrbitControls makeDefault enablePan={false} minDistance={2.2} maxDistance={6} />
      </Canvas>
      <small>{animationLabel ? `${animationLabel} · 自动循环 · 拖动旋转` : "拖动旋转 · 滚轮缩放 · 当前使用中性审查材质"}</small>
    </div>
  );
}
