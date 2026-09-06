import { useEffect, useRef } from 'react';

/**
 * FireflyBackground
 * 
 * Subtle, ambient firefly visual motif for Beacon.
 * Requirements:
 * - 5-8 tiny ambient fireflies with very low visual weight
 * - Slow, subtle wandering movement with warm amber glow
 * - One firefly smoothly follows the cursor with eased/smoothed lag
 * - Disabled or reduced on mobile (<768px)
 * - Respects prefers-reduced-motion
 * - Performs lightweight rendering on canvas and cleans up on unmount
 */
export default function FireflyBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    // Respect user's reduced-motion accessibility preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mediaQuery.matches) return;

    // Substantially reduce / disable on mobile devices to preserve battery and CPU
    if (window.innerWidth < 768) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // Mouse coordinates with smoothed easing
    const mouse = {
      x: width * 0.5,
      y: height * 0.35,
      targetX: width * 0.5,
      targetY: height * 0.35,
      hasMoved: false,
    };

    const handleMouseMove = (e) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
      mouse.hasMoved = true;
    };
    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    // 6 ambient fireflies
    const ambientCount = 6;
    const fireflies = [];

    for (let i = 0; i < ambientCount; i++) {
      fireflies.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        radius: 1.2 + Math.random() * 0.7,
        baseAlpha: 0.22 + Math.random() * 0.22,
        pulseSpeed: 0.012 + Math.random() * 0.018,
        phase: Math.random() * Math.PI * 2,
      });
    }

    // 1 cursor firefly that smoothly lags behind cursor
    const cursorFirefly = {
      radius: 1.7,
      baseAlpha: 0.42,
      pulseSpeed: 0.025,
      phase: 0,
    };

    let frameCount = 0;

    const render = () => {
      frameCount++;
      ctx.clearRect(0, 0, width, height);

      // Render ambient fireflies
      for (let i = 0; i < fireflies.length; i++) {
        const f = fireflies[i];
        f.phase += f.pulseSpeed;
        const currentAlpha = f.baseAlpha * (0.65 + 0.35 * Math.sin(f.phase));

        f.x += f.vx;
        f.y += f.vy;

        // Subtle wandering acceleration
        if (frameCount % 60 === 0) {
          f.vx += (Math.random() - 0.5) * 0.06;
          f.vy += (Math.random() - 0.5) * 0.06;
          // Clamp velocity
          const speed = Math.hypot(f.vx, f.vy);
          if (speed > 0.38) {
            f.vx = (f.vx / speed) * 0.38;
            f.vy = (f.vy / speed) * 0.38;
          }
        }

        // Soft screen bounds wrap
        if (f.x < -20) f.x = width + 20;
        if (f.x > width + 20) f.x = -20;
        if (f.y < -20) f.y = height + 20;
        if (f.y > height + 20) f.y = -20;

        // Draw soft ambient glow
        const glowRadius = f.radius * 6;
        const gradient = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, glowRadius);
        gradient.addColorStop(0, `rgba(245, 158, 11, ${currentAlpha * 0.45})`);
        gradient.addColorStop(0.5, `rgba(245, 158, 11, ${currentAlpha * 0.12})`);
        gradient.addColorStop(1, 'rgba(245, 158, 11, 0)');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(f.x, f.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();

        // Draw core ember
        ctx.fillStyle = `rgba(255, 230, 160, ${currentAlpha})`;
        ctx.beginPath();
        ctx.arc(f.x, f.y, f.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Render cursor firefly with lag
      if (mouse.hasMoved) {
        // Easing interpolation (lag factor 0.045)
        mouse.x += (mouse.targetX - mouse.x) * 0.045;
        mouse.y += (mouse.targetY - mouse.y) * 0.045;

        cursorFirefly.phase += cursorFirefly.pulseSpeed;
        const curAlpha = cursorFirefly.baseAlpha * (0.7 + 0.3 * Math.sin(cursorFirefly.phase));

        const glowRadius = cursorFirefly.radius * 7;
        const grad = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, glowRadius);
        grad.addColorStop(0, `rgba(245, 158, 11, ${curAlpha * 0.55})`);
        grad.addColorStop(0.5, `rgba(245, 158, 11, ${curAlpha * 0.16})`);
        grad.addColorStop(1, 'rgba(245, 158, 11, 0)');

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(255, 240, 190, ${curAlpha})`;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, cursorFirefly.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="firefly-canvas"
      aria-hidden="true"
    />
  );
}
