import { Component, Suspense, useEffect, useRef, type ErrorInfo, type ReactNode } from "react";
import { Grid, Html, OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { PreviewFocus } from "../lib/preview-focus";
import type { VisibilityGroup } from "../lib/registry";
import { applyHairPreviewDebugMaterial, applyHairPreviewParameters, applyPreviewVisibility, blinkStateAt, preparePreviewScene, type BlinkState, type HairPreviewParameterReport, type HairPreviewParameters } from "../lib/scene-preparation";

export type CameraView = "front" | "right" | "back" | "left" | "free";
export type VisibilityState = Record<VisibilityGroup, boolean>;

interface ActorPreviewProps {
  modelUrl: string;
  view: CameraView;
  playing: boolean;
  normalizedTime: number;
  visibility: VisibilityState;
  showBody: boolean;
  focus: PreviewFocus;
  hairParameters: HairPreviewParameters;
  hairDebugMaterial: boolean;
  onHairParameterReport: (report: HairPreviewParameterReport) => void;
  onTimeChange: (value: number) => void;
  onDuration: (duration: number, animationName: string) => void;
  onModelError: () => void;
  onOrbitStart: () => void;
}

interface BoundaryProps {
  children: ReactNode;
  onError: () => void;
}

interface BoundaryState {
  failed: boolean;
}

class PreviewErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Actor preview failed", error, info);
    this.props.onError();
  }

  render() {
    if (this.state.failed) {
      return <PreviewFallback label="GLB 解析失败" />;
    }
    return this.props.children;
  }
}

function PreviewFallback({ label }: { label: string }) {
  return (
    <div className="preview-fallback" role="status">
      <div className="fallback-orbit orbit-a" />
      <div className="fallback-orbit orbit-b" />
      <div className="fallback-actor" aria-hidden="true">
        <span className="fallback-head" />
        <span className="fallback-body" />
        <span className="fallback-leg leg-left" />
        <span className="fallback-leg leg-right" />
      </div>
      <p>{label}</p>
    </div>
  );
}

function CameraRig({ view, focus }: { view: CameraView; focus: PreviewFocus }) {
  const { camera, controls } = useThree();
  const pendingView = useRef(true);
  useEffect(() => {
    pendingView.current = true;
  }, [focus, view]);
  useFrame(() => {
    if (view === "free" || !pendingView.current) return;
    const [targetX, targetY, targetZ] = focus.target;
    const [x, y, z] = [targetX, targetY, targetZ + focus.distance];
    camera.position.set(x, y, z);
    camera.lookAt(...focus.target);
    camera.updateProjectionMatrix();
    const orbit = controls as { target?: THREE.Vector3; update?: () => void } | null;
    orbit?.target?.set(...focus.target);
    orbit?.update?.();
    pendingView.current = false;
  });
  return null;
}

function FixedViewOrientation({ view, children }: { view: CameraView; children: ReactNode }) {
  const lastRotation = useRef(0);
  const rotations: Record<Exclude<CameraView, "free">, number> = {
    front: 0,
    right: -Math.PI / 2,
    back: Math.PI,
    left: Math.PI / 2,
  };
  if (view !== "free") lastRotation.current = rotations[view];
  return <group rotation={[0, lastRotation.current, 0]}>{children}</group>;
}

function ActorModel({
  modelUrl,
  playing,
  normalizedTime,
  visibility,
  showBody,
  hairParameters,
  hairDebugMaterial,
  onHairParameterReport,
  onTimeChange,
  onDuration,
}: Omit<ActorPreviewProps, "view" | "focus" | "onModelError" | "onOrbitStart">) {
  const gltf = useGLTF(modelUrl);
  // A regular Object3D.clone(true) does not preserve SkinnedMesh -> bone
  // references. F001 mounts one GLB instance, so using the loader-owned scene
  // directly keeps Actor, face, garments and shoes on the same skeleton.
  const scene = gltf.scene;
  const { actions, names, mixer } = useAnimations(gltf.animations, scene);
  const action = names.length > 0 ? actions[names[0]] : undefined;
  const lastReport = useRef(0);
  const currentBlink = useRef<BlinkState>("open");

  useEffect(() => {
    preparePreviewScene(scene);
  }, [scene]);

  useEffect(() => {
    applyHairPreviewParameters(scene, hairParameters);
    onHairParameterReport(scene.userData.assetsstudio_hair_parameter_report as HairPreviewParameterReport);
  }, [hairParameters, onHairParameterReport, scene]);

  useEffect(() => {
    applyHairPreviewDebugMaterial(scene, hairDebugMaterial);
  }, [hairDebugMaterial, scene]);

  useEffect(() => {
    applyPreviewVisibility(scene, visibility, currentBlink.current, showBody);
  }, [scene, showBody, visibility]);

  useEffect(() => {
    if (!action) {
      onDuration(0, "未找到动画");
      return;
    }
    action.reset().setLoop(THREE.LoopRepeat, Number.POSITIVE_INFINITY).play();
    action.paused = !playing;
    onDuration(action.getClip().duration, action.getClip().name);
    return () => {
      action.stop();
    };
  }, [action, onDuration]);

  useEffect(() => {
    if (action) action.paused = !playing;
  }, [action, playing]);

  useEffect(() => {
    if (!action || playing) return;
    action.time = THREE.MathUtils.clamp(normalizedTime, 0, 1) * action.getClip().duration;
    mixer.update(0);
    currentBlink.current = blinkStateAt(normalizedTime);
    applyPreviewVisibility(scene, visibility, currentBlink.current, showBody);
  }, [action, mixer, normalizedTime, playing, scene, showBody, visibility]);

  useFrame((_, delta) => {
    // The loader-owned scene is shared with the animation mixer. Reassert the
    // presentation contract every frame so an isolated preview cannot be
    // undone by a late mixer/loader update.
    applyPreviewVisibility(scene, visibility, currentBlink.current, showBody);
    if (!action || !playing) return;
    mixer.update(delta);
    const duration = action.getClip().duration || 1;
    const normalized = (action.time % duration) / duration;
    const nextBlink = blinkStateAt(normalized);
    if (nextBlink !== currentBlink.current) {
      currentBlink.current = nextBlink;
      applyPreviewVisibility(scene, visibility, nextBlink, showBody);
    }
    lastReport.current += delta;
    if (lastReport.current > 0.08) {
      lastReport.current = 0;
      onTimeChange(normalized);
    }
  });

  return <primitive object={scene} />;
}

export function ActorPreview(props: ActorPreviewProps) {
  return (
    <PreviewErrorBoundary onError={props.onModelError}>
      <Canvas
        className="actor-canvas"
        camera={{ position: [0, 1.33, 5.05], fov: 34, near: 0.01, far: 100 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping }}
      >
        <color attach="background" args={["#161a26"]} />
        <fog attach="fog" args={["#161a26", 4.5, 8]} />
        <ambientLight intensity={1.65} />
        <directionalLight position={[-3, -4, 6]} intensity={3.2} color="#fff0dc" />
        <directionalLight position={[4, 2, 3]} intensity={1.6} color="#9cc8ff" />
        <Suspense
          fallback={
            <Html center>
              <div className="canvas-loading">正在载入 Actor…</div>
            </Html>
          }
        >
          <FixedViewOrientation view={props.view}><ActorModel {...props} /></FixedViewOrientation>
        </Suspense>
        <Grid
          args={[8, 8]}
          position={[0, 0, 0]}
          cellSize={0.2}
          cellThickness={0.45}
          cellColor="#46536b"
          sectionSize={1}
          sectionThickness={0.8}
          sectionColor="#7182a0"
          fadeDistance={5}
          fadeStrength={1.5}
          infiniteGrid
        />
        <CameraRig view={props.view} focus={props.focus} />
        <OrbitControls
          key={props.focus.target.join(":")}
          makeDefault
          enabled
          target={props.focus.target}
          minDistance={1.1}
          maxDistance={8}
          enablePan={false}
          onStart={props.onOrbitStart}
        />
      </Canvas>
    </PreviewErrorBoundary>
  );
}

export { PreviewFallback };
