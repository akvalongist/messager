/**
 * Particle animation layer for the messenger background.
 */
class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.mouse = { x: null, y: null, radius: 150 };

        this.particleCount = 80;
        this.speed = 0.5;
        this.lineDistance = 150;
        this.particleSize = 2;

        this.resize();
        this.init();
        this.animate();

        window.addEventListener('resize', () => this.resize());
        window.addEventListener('mousemove', (event) => {
            this.mouse.x = event.x;
            this.mouse.y = event.y;
        });
        window.addEventListener('mouseout', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        });
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    init() {
        this.particles = [];
        for (let i = 0; i < this.particleCount; i += 1) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * this.speed,
                vy: (Math.random() - 0.5) * this.speed,
                size: Math.random() * this.particleSize + 0.5,
                opacity: Math.random() * 0.5 + 0.2,
            });
        }
    }

    setParticleCount(nextCount) {
        const parsed = Number(nextCount);
        if (!Number.isFinite(parsed)) return;

        const normalized = Math.max(0, Math.min(200, Math.round(parsed)));
        if (normalized === this.particleCount) return;

        this.particleCount = normalized;
        this.init();
    }

    getThemeColor() {
        const style = getComputedStyle(document.documentElement);
        const hue = style.getPropertyValue('--theme-hue').trim() || '260';
        const sat = style.getPropertyValue('--theme-saturation').trim() || '70%';
        return { hue: parseInt(hue, 10), sat };
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const { hue, sat } = this.getThemeColor();

        for (let i = 0; i < this.particles.length; i += 1) {
            const particle = this.particles[i];

            particle.x += particle.vx;
            particle.y += particle.vy;

            if (particle.x < 0 || particle.x > this.canvas.width) particle.vx *= -1;
            if (particle.y < 0 || particle.y > this.canvas.height) particle.vy *= -1;

            if (this.mouse.x !== null) {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < this.mouse.radius) {
                    const force = (this.mouse.radius - dist) / this.mouse.radius;
                    particle.vx += dx * force * 0.0005;
                    particle.vy += dy * force * 0.0005;
                }
            }

            const maxSpeed = 1.5;
            const currentSpeed = Math.sqrt(particle.vx * particle.vx + particle.vy * particle.vy);
            if (currentSpeed > maxSpeed) {
                particle.vx = (particle.vx / currentSpeed) * maxSpeed;
                particle.vy = (particle.vy / currentSpeed) * maxSpeed;
            }

            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.ctx.fillStyle = `hsla(${hue}, ${sat}, 70%, ${particle.opacity})`;
            this.ctx.fill();

            for (let j = i + 1; j < this.particles.length; j += 1) {
                const nextParticle = this.particles[j];
                const dx = particle.x - nextParticle.x;
                const dy = particle.y - nextParticle.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < this.lineDistance) {
                    const opacity = (1 - dist / this.lineDistance) * 0.15;
                    this.ctx.beginPath();
                    this.ctx.moveTo(particle.x, particle.y);
                    this.ctx.lineTo(nextParticle.x, nextParticle.y);
                    this.ctx.strokeStyle = `hsla(${hue}, ${sat}, 60%, ${opacity})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.stroke();
                }
            }

            if (this.mouse.x !== null) {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < this.mouse.radius) {
                    const opacity = (1 - dist / this.mouse.radius) * 0.3;
                    this.ctx.beginPath();
                    this.ctx.moveTo(particle.x, particle.y);
                    this.ctx.lineTo(this.mouse.x, this.mouse.y);
                    this.ctx.strokeStyle = `hsla(${hue}, ${sat}, 70%, ${opacity})`;
                    this.ctx.lineWidth = 0.8;
                    this.ctx.stroke();
                }
            }
        }

        requestAnimationFrame(() => this.animate());
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particle-canvas');
    if (canvas) {
        window.particleSystem = new ParticleSystem(canvas);
    }
});
