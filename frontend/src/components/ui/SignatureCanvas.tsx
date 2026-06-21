'use client';
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';

export interface SignatureCanvasHandle {
  clear: () => void;
  toBase64: () => string | null;
  isEmpty: () => boolean;
}

interface Props {
  onChange?: (hasContent: boolean) => void;
}

export const SignatureCanvas = forwardRef<SignatureCanvasHandle, Props>(
  function SignatureCanvas({ onChange }, ref) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
    const drawing = useRef(false);
    const hasContent = useRef(false);
    const onChangeRef = useRef(onChange);

    useEffect(() => {
      onChangeRef.current = onChange;
    }, [onChange]);

    useImperativeHandle(ref, () => ({
      clear() {
        const c = canvasRef.current;
        const ctx = ctxRef.current;
        if (!c || !ctx) return;
        ctx.clearRect(0, 0, c.width, c.height);
        hasContent.current = false;
        onChangeRef.current?.(false);
      },
      toBase64() {
        const c = canvasRef.current;
        if (!c || !hasContent.current) return null;
        return c.toDataURL('image/png').split(',')[1] ?? null;
      },
      isEmpty() {
        return !hasContent.current;
      },
    }));

    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctxRef.current = ctx;

      ctx.lineWidth = 2.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#1e293b';

      function getPos(e: MouseEvent | TouchEvent) {
        // Handlers fire on the canvas element — canvasRef.current is guaranteed non-null
        const el = canvasRef.current!;
        const rect = el.getBoundingClientRect();
        const src = 'touches' in e ? e.touches[0] : e;
        return {
          x: ((src.clientX - rect.left) * el.width) / rect.width,
          y: ((src.clientY - rect.top) * el.height) / rect.height,
        };
      }

      function onStart(e: MouseEvent | TouchEvent) {
        e.preventDefault();
        drawing.current = true;
        // ctxRef.current set above in this same effect, non-null while canvas is mounted
        const c = ctxRef.current!;
        const { x, y } = getPos(e);
        c.beginPath();
        c.moveTo(x, y);
      }

      function onMove(e: MouseEvent | TouchEvent) {
        if (!drawing.current) return;
        e.preventDefault();
        const c = ctxRef.current!;
        const { x, y } = getPos(e);
        c.lineTo(x, y);
        c.stroke();
        if (!hasContent.current) {
          hasContent.current = true;
          onChangeRef.current?.(true);
        }
      }

      function onEnd() {
        drawing.current = false;
      }

      canvas.addEventListener('mousedown', onStart);
      canvas.addEventListener('mousemove', onMove);
      canvas.addEventListener('mouseup', onEnd);
      canvas.addEventListener('mouseleave', onEnd);
      canvas.addEventListener('touchstart', onStart, { passive: false });
      canvas.addEventListener('touchmove', onMove, { passive: false });
      canvas.addEventListener('touchend', onEnd);

      return () => {
        canvas.removeEventListener('mousedown', onStart);
        canvas.removeEventListener('mousemove', onMove);
        canvas.removeEventListener('mouseup', onEnd);
        canvas.removeEventListener('mouseleave', onEnd);
        canvas.removeEventListener('touchstart', onStart);
        canvas.removeEventListener('touchmove', onMove);
        canvas.removeEventListener('touchend', onEnd);
        ctxRef.current = null;
      };
    }, []);

    return (
      <canvas
        ref={canvasRef}
        width={600}
        height={160}
        className="w-full cursor-crosshair touch-none rounded-lg border-2 border-dashed border-gray-300 bg-white"
      />
    );
  },
);
