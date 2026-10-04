import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Icosahedron, Sphere, Ring, Points, PointMaterial } from '@react-three/drei';
import * as THREE from 'three';

const colors = {
  primary: '#083fc3',
  primaryLight: '#2f6bff',
  primaryGlow: '#5b8cff',
  primarySoft: '#9db9ff',
  primaryDark: '#052a82',
  error: '#ff3b4e',
};

const HUDRing = ({ radius, width, speed, segments, opacity, state, reverse = false, rms = 0 }: any) => {
  const ref = useRef<THREE.Group>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);

  useFrame((_, delta) => {
    if (!ref.current) return;
    let currentSpeed = speed;
    let targetColor = colors.primaryLight;
    
    if (state === 'THINKING') currentSpeed = speed * 4.0;
    if (state === 'SPEAKING') currentSpeed = speed * 2.0 + (rms / 100) * 3.0;
    if (state === 'LISTENING') currentSpeed = speed * 1.5 + (rms / 100) * 2.5;
    if (state === 'TOOL_EXECUTION') currentSpeed = speed * -5.0; // rapid reverse cadence
    if (state === 'ERROR') {
      currentSpeed = speed * 10.0;
      targetColor = colors.error;
    }

    ref.current.rotation.z += (reverse ? -1 : 1) * delta * currentSpeed;

    if (matRef.current) {
        matRef.current.color.lerp(new THREE.Color(targetColor), 0.1);
    }
  });

  const rings = [];
  const arcLength = (Math.PI * 2) / segments;
  for (let i = 0; i < segments; i++) {
    rings.push(
      <Ring key={i} args={[radius, radius + width, 32, 1, i * arcLength, arcLength * 0.8]}>
        <meshBasicMaterial ref={i===0?matRef:null} color={colors.primaryLight} transparent opacity={opacity} side={THREE.DoubleSide} />
      </Ring>
    );
  }

  return <group ref={ref}>{rings}</group>;
};

const Lattice = ({ state, rms = 0 }: { state: string, rms?: number }) => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);
  
  useFrame(({ clock }, delta) => {
    if (!meshRef.current || !matRef.current) return;
    
    let targetScale = 1.0;
    let targetColor = colors.primary;
    let rotSpeed = 0.2;
    
    if (state === 'LISTENING') {
        targetScale = 0.95 + (rms / 100) * 0.15;
        targetColor = colors.primaryGlow;
        rotSpeed = 0.5 + (rms / 100) * 1.5;
    } else if (state === 'THINKING') {
        targetScale = 1.05;
        targetColor = colors.primaryLight;
        rotSpeed = 1.5;
    } else if (state === 'SPEAKING') {
        targetScale = 1.1 + Math.sin(clock.getElapsedTime() * 10) * 0.05 + (rms / 100) * 0.2;
        targetColor = colors.primarySoft;
        rotSpeed = 0.8 + (rms / 100) * 2.0;
    } else if (state === 'TOOL_EXECUTION') {
        targetScale = 0.9;
        targetColor = colors.primaryDark;
        rotSpeed = 4.0;
    } else if (state === 'ERROR') {
        targetScale = 1.3 + (Math.random() - 0.5) * 0.2;
        targetColor = colors.error;
        rotSpeed = 5.0;
        meshRef.current.position.set((Math.random()-0.5)*0.1, (Math.random()-0.5)*0.1, 0);
    } else {
        meshRef.current.position.set(0,0,0);
        targetScale = 1.0 + Math.sin(clock.getElapsedTime() * 1.5) * 0.02;
    }

    if (state !== 'ERROR') {
        meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
        meshRef.current.position.lerp(new THREE.Vector3(0,0,0), 0.1);
    } else {
        meshRef.current.scale.set(targetScale, targetScale, targetScale);
    }
    
    meshRef.current.rotation.y += delta * rotSpeed;
    meshRef.current.rotation.x += delta * rotSpeed * 0.5;
    
    matRef.current.color.lerp(new THREE.Color(targetColor), 0.1);
  });

  return (
    <Icosahedron ref={meshRef} args={[1.2, 2]}>
      <meshBasicMaterial ref={matRef} color={colors.primary} wireframe transparent opacity={0.4} />
    </Icosahedron>
  );
};

const Nucleus = ({ state, rms = 0 }: { state: string, rms?: number }) => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);
  const lightRef = useRef<THREE.PointLight>(null!);

  useFrame(({ clock }) => {
    if (!meshRef.current || !matRef.current) return;
    const t = clock.getElapsedTime();
    
    let scale = 1.0;
    let color = colors.primaryLight;
    
    if (state === 'IDLE') {
        scale = 1.0 + Math.sin(t * 1.5) * 0.1;
    } else if (state === 'THINKING') {
        scale = 1.1 + Math.sin(t * 8.0) * 0.15;
        color = colors.primaryGlow;
    } else if (state === 'SPEAKING') {
        scale = 1.2 + Math.sin(t * 15.0) * 0.2 + (rms / 100) * 0.4;
        color = '#cfe0ff';
    } else if (state === 'LISTENING') {
        scale = 1.05 + Math.sin(t * 4.0) * 0.05 + (rms / 100) * 0.25;
        color = colors.primarySoft;
    } else if (state === 'TOOL_EXECUTION') {
        scale = 0.8 + Math.sin(t * 20.0) * 0.03;
        color = colors.primaryLight;
    } else if (state === 'ERROR') {
        scale = 1.5 + (Math.random() - 0.5) * 0.5;
        color = colors.error;
    }

    if (state !== 'ERROR') {
        meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);
    } else {
        meshRef.current.scale.set(scale, scale, scale);
    }
    
    const targetColor = new THREE.Color(color);
    matRef.current.color.lerp(targetColor, 0.1);
    if(lightRef.current) lightRef.current.color.lerp(targetColor, 0.1);
  });

  return (
    <group>
      <pointLight ref={lightRef} intensity={2.0} distance={5} />
      <Sphere ref={meshRef} args={[0.4, 32, 32]}>
        <meshBasicMaterial ref={matRef} color={colors.primaryLight} transparent opacity={0.9} />
      </Sphere>
    </group>
  );
};

const EnergyFilaments = ({ state, rms = 0 }: { state: string, rms?: number }) => {
  const points = useRef<THREE.Points>(null!);
  const matRef = useRef<THREE.PointsMaterial>(null!);
  
  const count = 300;
  const particlesPosition = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const distance = 0.5 + Math.random() * 0.7;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = distance * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = distance * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = distance * Math.cos(phi);
    }
    return positions;
  }, [count]);

  useFrame((_, delta) => {
    if (!points.current) return;
    let speed = 0.2;
    let color = colors.primaryGlow;
    
    if (state === 'LISTENING') { speed = 0.2 + (rms / 100) * 2.0; }
    if (state === 'THINKING') { speed = 2.0; color = colors.primaryLight; }
    if (state === 'SPEAKING') { speed = 1.0 + (rms / 100) * 3.0; }
    if (state === 'TOOL_EXECUTION') { speed = -3.0; color = colors.primary; }
    if (state === 'ERROR') { speed = 5.0; color = colors.error; }

    points.current.rotation.y -= delta * speed;
    points.current.rotation.x += delta * speed * 0.5;
    
    if (matRef.current) {
        matRef.current.color.lerp(new THREE.Color(color), 0.1);
    }
  });

  return (
    <Points ref={points} positions={particlesPosition} stride={3} frustumCulled={false}>
      <PointMaterial ref={matRef} transparent color={colors.primaryGlow} size={0.02} sizeAttenuation={true} depthWrite={false} blending={THREE.AdditiveBlending} />
    </Points>
  );
};

export const Core3D: React.FC<{state: string, isVisible: boolean, rms?: number}> = ({ state, isVisible, rms = 0 }) => {
  return (
    <div style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, zIndex: 0 }}>
      <Canvas frameloop={isVisible ? 'always' : 'demand'} camera={{ position: [0, 0, 4.5], fov: 50 }} style={{ background: 'transparent' }} dpr={[1, 2]}>
        
        <Nucleus state={state} rms={rms} />
        <Lattice state={state} rms={rms} />
        <EnergyFilaments state={state} rms={rms} />
        
        {/* HUD Rings facing camera */}
        <HUDRing radius={1.7} width={0.02} speed={0.5} segments={3} opacity={0.6} state={state} rms={rms} />
        <HUDRing radius={1.85} width={0.01} speed={0.3} segments={5} opacity={0.4} state={state} reverse rms={rms} />
        <HUDRing radius={2.0} width={0.03} speed={0.8} segments={2} opacity={0.3} state={state} rms={rms} />
        <HUDRing radius={2.15} width={0.005} speed={0.2} segments={8} opacity={0.2} state={state} reverse rms={rms} />

      </Canvas>
    </div>
  );
};
