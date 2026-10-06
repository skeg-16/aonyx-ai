import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Icosahedron, Sphere, Ring, Points, PointMaterial } from '@react-three/drei';
import * as THREE from 'three';
import { EffectComposer, Bloom, Vignette, Noise, Scanline } from '@react-three/postprocessing';
import { live, audioBus, interaction, updateFrame } from './shared';

const colors = {
  primary: '#083fc3',
  primaryLight: '#2f6bff',
  primaryGlow: '#5b8cff',
  primarySoft: '#9db9ff',
  primaryDark: '#052a82',
  error: '#ff3b4e',
  hover: '#00d9ff',
};

const HUDRing = ({ radius, width, speed, segments, opacity, reverse = false }: any) => {
  const ref = useRef<THREE.Group>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const state = live.state;
    const rms = audioBus.raw * 100;
    const isHovered = interaction.hoverT > 0.5;

    let currentSpeed = speed;
    let targetColor = isHovered ? colors.hover : colors.primaryLight;
    
    if (state === 'THINKING') currentSpeed = speed * 4.0;
    if (state === 'SPEAKING') currentSpeed = speed * 2.0 + (rms / 100) * 3.0;
    if (state === 'LISTENING') currentSpeed = speed * 1.5 + (rms / 100) * 2.5;
    if (state === 'TOOL_EXECUTION') currentSpeed = speed * -5.0; // rapid reverse cadence
    if (state === 'ERROR') {
      currentSpeed = speed * 10.0;
      targetColor = colors.error;
    }

    if (isHovered && state === 'IDLE') {
        currentSpeed = speed * 2.0;
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

const Lattice = () => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);
  
  useFrame(({ clock }, delta) => {
    if (!meshRef.current || !matRef.current) return;
    const state = live.state;
    const rms = audioBus.raw * 100;
    const isHovered = interaction.hoverT > 0.5;
    
    let targetScale = 1.0;
    let targetColor = isHovered ? colors.hover : colors.primary;
    let rotSpeed = isHovered ? 0.4 : 0.2;
    
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

const Nucleus = () => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const innerRef = useRef<THREE.Mesh>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);
  const lightRef = useRef<THREE.PointLight>(null!);

  useFrame(({ clock }) => {
    if (!meshRef.current || !matRef.current || !innerRef.current) return;
    const state = live.state;
    const rms = audioBus.raw * 100;
    const isHovered = interaction.hoverT > 0.5;
    const t = clock.getElapsedTime();
    
    let scale = 1.0;
    let color = isHovered ? colors.hover : colors.primaryLight;
    
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

    if (isHovered && state === 'IDLE') {
        scale *= 1.05;
    }

    if (state !== 'ERROR') {
        meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);
        innerRef.current.scale.lerp(new THREE.Vector3(scale * 1.15, scale * 1.15, scale * 1.15), 0.1);
    } else {
        meshRef.current.scale.set(scale, scale, scale);
        innerRef.current.scale.set(scale * 1.15, scale * 1.15, scale * 1.15);
    }
    
    innerRef.current.rotation.y += 0.02;
    innerRef.current.rotation.x += 0.01;
    
    const targetColor = new THREE.Color(color);
    matRef.current.color.lerp(targetColor, 0.1);
    if(lightRef.current) lightRef.current.color.lerp(targetColor, 0.1);
  });

  return (
    <group>
      <pointLight ref={lightRef} intensity={2.0} distance={6} />
      <Sphere ref={meshRef} args={[0.35, 32, 32]}>
        <meshBasicMaterial ref={matRef} color={colors.primaryLight} transparent opacity={0.9} />
      </Sphere>
      <Icosahedron ref={innerRef} args={[0.4, 2]}>
        <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.2} blending={THREE.AdditiveBlending} />
      </Icosahedron>
    </group>
  );
};

const EnergyFilaments = () => {
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
    const state = live.state;
    const rms = audioBus.raw * 100;
    const isHovered = interaction.hoverT > 0.5;
    let speed = isHovered ? 0.4 : 0.2;
    let color = isHovered ? colors.hover : colors.primaryGlow;
    
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

const InnerGlow = () => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);

  useFrame(({ clock }) => {
    if (!meshRef.current || !matRef.current) return;
    const state = live.state;
    const rms = audioBus.raw * 100;
    const isHovered = interaction.hoverT > 0.5;
    const t = clock.getElapsedTime();
    let scale = 1.0;
    
    if (state === 'IDLE') scale = 1.0 + Math.sin(t * 1.2) * 0.05;
    else if (state === 'THINKING') scale = 1.1 + Math.sin(t * 5.0) * 0.1;
    else if (state === 'SPEAKING') scale = 1.1 + (rms / 100) * 0.3;
    else if (state === 'TOOL_EXECUTION') scale = 0.9 + Math.sin(t * 15.0) * 0.05;
    else if (state === 'ERROR') scale = 1.2 + (Math.random() - 0.5) * 0.1;

    if (isHovered && state === 'IDLE') {
        scale *= 1.1;
    }

    meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);
    matRef.current.color.lerp(new THREE.Color(isHovered ? colors.hover : colors.primaryGlow), 0.1);
    matRef.current.opacity = isHovered ? 0.3 : 0.15;
  });

  return (
    <Icosahedron ref={meshRef} args={[0.7, 4]}>
      <meshBasicMaterial ref={matRef} color={colors.primaryGlow} transparent opacity={0.15} blending={THREE.AdditiveBlending} depthWrite={false} />
    </Icosahedron>
  );
};

const OuterShell = () => {
  const meshRef = useRef<THREE.Mesh>(null!);
  const matRef = useRef<THREE.MeshBasicMaterial>(null!);
  
  useFrame(({ clock }, delta) => {
    if (!meshRef.current || !matRef.current) return;
    const state = live.state;
    const rms = audioBus.raw * 100;
    const isHovered = interaction.hoverT > 0.5;
    
    let targetScale = 1.0;
    let targetColor = isHovered ? colors.hover : colors.primaryDark;
    let rotSpeed = isHovered ? -0.2 : 0.1;
    
    if (state === 'LISTENING') {
        targetScale = 0.98;
        targetColor = colors.primary;
        rotSpeed = 0.3 + (rms / 100) * 1.0;
    } else if (state === 'THINKING') {
        targetScale = 1.02;
        rotSpeed = 0.8;
    } else if (state === 'SPEAKING') {
        targetScale = 1.05 + (rms / 100) * 0.1;
        targetColor = colors.primary;
        rotSpeed = 0.4 + (rms / 100) * 1.5;
    } else if (state === 'TOOL_EXECUTION') {
        targetScale = 0.95;
        targetColor = colors.primaryLight;
        rotSpeed = 2.0;
    } else if (state === 'ERROR') {
        targetScale = 1.1;
        targetColor = colors.error;
        rotSpeed = 3.0;
    } else {
        targetScale = 1.0 + Math.sin(clock.getElapsedTime() * 1.0) * 0.01;
    }

    if (isHovered && state === 'IDLE') {
        targetScale *= 1.03;
    }

    meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
    meshRef.current.rotation.y -= delta * rotSpeed * 0.5;
    meshRef.current.rotation.z += delta * rotSpeed * 0.2;
    
    matRef.current.color.lerp(new THREE.Color(targetColor), 0.05);
    matRef.current.opacity = isHovered ? 0.3 : 0.2;
  });

  return (
    <Icosahedron ref={meshRef} args={[1.5, 1]}>
      <meshBasicMaterial ref={matRef} color={colors.primaryDark} wireframe transparent opacity={0.2} blending={THREE.AdditiveBlending} />
    </Icosahedron>
  );
};

const SystemLoop = () => {
    useFrame((_, delta) => updateFrame(delta));
    return null;
};

const BackgroundParticles = () => {
    const count = 400;
    const positions = useMemo(() => {
        const p = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            p[i*3] = (Math.random() - 0.5) * 20;
            p[i*3+1] = (Math.random() - 0.5) * 20;
            p[i*3+2] = (Math.random() - 0.5) * 15 - 5;
        }
        return p;
    }, []);
    const ref = useRef<THREE.Points>(null!);
    
    useFrame(({ clock }) => {
        if (!ref.current) return;
        const st = live.state;
        const t = clock.getElapsedTime() * 0.05;
        
        ref.current.rotation.y = t + interaction.px * 0.1;
        ref.current.rotation.x = interaction.py * 0.1;
        
        const s = ref.current.scale.x;
        const targetScale = (st === 'THINKING') ? 0.8 : ((st === 'LISTENING') ? 0.95 : 1.0);
        ref.current.scale.setScalar(s + (targetScale - s) * 0.05);
        
        if (st === 'THINKING') {
            ref.current.rotation.z += 0.005;
        }
    });

    return (
        <Points ref={ref} positions={positions} frustumCulled={false}>
            <PointMaterial color={colors.primarySoft} size={0.03} sizeAttenuation transparent opacity={0.3} blending={THREE.AdditiveBlending} depthWrite={false} />
        </Points>
    );
};

const PostProcessingBloom = ({ isCompact }: { isCompact: boolean }) => {
    const [intensity, setIntensity] = React.useState(isCompact ? 1.5 : 2.5);
    useFrame(() => {
        const isHovered = interaction.hoverT > 0.5;
        setIntensity(isCompact ? 1.5 : (isHovered ? 3.0 : 2.5));
    });
    return (
        <EffectComposer>
            <Bloom luminanceThreshold={0.15} luminanceSmoothing={0.9} height={300} intensity={intensity} />
            <Noise opacity={isCompact ? 0.02 : 0.03} />
            <Vignette eskil={false} offset={0.1} darkness={1.1} />
            <Scanline density={isCompact ? 1.5 : 2.0} opacity={0.05} />
        </EffectComposer>
    );
};

const CoreVisuals = () => {
    const groupRef = useRef<THREE.Group>(null!);
    
    useFrame(() => {
        if (!groupRef.current) return;
        
        if (interaction.dragging) {
            interaction.rotY += interaction.velX * 0.005;
            interaction.rotX += interaction.velY * 0.005;
            interaction.rotX = Math.max(-Math.PI/2.5, Math.min(Math.PI/2.5, interaction.rotX));
            interaction.velX *= 0.5; // decay quickly while dragging so it stops if mouse stops
            interaction.velY *= 0.5;
        } else {
            interaction.rotY += interaction.velX * 0.01;
            interaction.rotX += interaction.velY * 0.01;
            interaction.rotX = Math.max(-Math.PI/2.5, Math.min(Math.PI/2.5, interaction.rotX));
            interaction.velX *= 0.95; // inertia damping
            interaction.velY *= 0.95;
        }
        
        groupRef.current.rotation.y = interaction.rotY;
        groupRef.current.rotation.x = interaction.rotX;
    });

    return (
        <group ref={groupRef}>
            <Nucleus />
            <InnerGlow />
            <Lattice />
            <OuterShell />
            <EnergyFilaments />
        </group>
    );
};

export const Core3D: React.FC<{isVisible: boolean, isCompact?: boolean, onCoreClick?: () => void}> = ({ isVisible, isCompact = false, onCoreClick }) => {
  const [hovered, setHovered] = React.useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const HitBox = () => (
    <mesh 
      onPointerOver={() => { interaction.hoverT = 1; setHovered(true); }} 
      onPointerOut={() => { 
          interaction.hoverT = 0; setHovered(false); 
          interaction.dragging = false; 
      }}
      onPointerDown={(e) => {
          e.stopPropagation();
          interaction.dragging = true;
          interaction.velX = 0;
          interaction.velY = 0;
          dragStart.current = { x: e.clientX, y: e.clientY };
          (e.target as any).setPointerCapture(e.pointerId);
      }}
      onPointerUp={(e) => {
          e.stopPropagation();
          interaction.dragging = false;
          (e.target as any).releasePointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
          if (interaction.dragging) {
              interaction.velX = e.movementX;
              interaction.velY = e.movementY;
          }
      }}
      onClick={(e) => {
          const dx = e.clientX - dragStart.current.x;
          const dy = e.clientY - dragStart.current.y;
          if (Math.abs(dx) < 5 && Math.abs(dy) < 5) {
              onCoreClick?.();
          }
      }}
      visible={false}
    >
      <sphereGeometry args={[2.5, 16, 16]} />
      <meshBasicMaterial />
    </mesh>
  );

  return (
    <div style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, zIndex: 0, cursor: hovered ? (interaction.dragging ? 'grabbing' : 'pointer') : 'default' }}>
      <Canvas frameloop={isVisible ? 'always' : 'demand'} camera={{ position: [0, 0, isCompact ? 4.5 : 3.8], fov: isCompact ? 50 : 60 }} style={{ background: 'transparent' }} dpr={[1, 2]}>
        <SystemLoop />
        
        <BackgroundParticles />

        <HitBox />
        
        <CoreVisuals />
        
        {/* HUD Rings facing camera - Scale up slightly in full screen */}
        <group scale={isCompact ? 1.0 : 1.2}>
          <HUDRing radius={1.7} width={0.02} speed={0.5} segments={3} opacity={0.6} />
          <HUDRing radius={1.85} width={0.01} speed={0.3} segments={6} opacity={0.4} reverse />
          <HUDRing radius={2.0} width={0.03} speed={0.8} segments={2} opacity={0.3} />
          <HUDRing radius={2.15} width={0.005} speed={0.2} segments={12} opacity={0.2} reverse />
          <HUDRing radius={2.3} width={0.01} speed={0.1} segments={4} opacity={0.15} />
        </group>

        <PostProcessingBloom isCompact={isCompact} />
      </Canvas>
    </div>
  );
};

