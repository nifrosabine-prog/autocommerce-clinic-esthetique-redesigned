import React, { useRef, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Eraser, Pencil, RotateCcw } from 'lucide-react';

interface SimulationCrayonPadProps {
  imageUrl: string;
  onSave: (maskBase64: string) => void;
  onCancel: () => void;
}

export function SimulationCrayonPad({ imageUrl, onSave, onCancel }: SimulationCrayonPadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const contextRef = useRef<CanvasRenderingContext2D | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [mode, setMode] = useState<'draw' | 'erase'>('draw');
  const [brushSize, setBrushSize] = useState(20);
  const [canvasReady, setCanvasReady] = useState(false);
  const [hasMark, setHasMark] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Ajuster la taille du canvas à l'image
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = imageUrl;
    img.onload = () => {
      const displayWidth = Math.min(window.innerWidth * 0.8, 600);
      const scale = displayWidth / img.width;
      canvas.width = displayWidth;
      canvas.height = img.height * scale;
      setCanvasReady(true);
      setHasMark(false);

      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = 'rgba(255, 0, 0, 0.5)';
        ctx.lineWidth = brushSize;
        contextRef.current = ctx;
        
        // Fond initial : blanc opaque (sera la zone NON modifiée)
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // On utilise 'destination-out' pour rendre transparent là où on dessine
        // Car OpenAI veut du transparent pour les zones à éditer
        ctx.globalCompositeOperation = 'destination-out';
      }
    };
  }, [imageUrl]);

  useEffect(() => {
    if (contextRef.current) {
      contextRef.current.lineWidth = brushSize;
      contextRef.current.globalCompositeOperation = mode === 'draw' ? 'destination-out' : 'source-over';
      // Si on repasse en mode source-over (gomme), on remet du blanc opaque
      if (mode === 'erase') {
        contextRef.current.strokeStyle = 'white';
      }
    }
  }, [mode, brushSize]);

  const startDrawing = ({ nativeEvent }: React.MouseEvent | React.TouchEvent) => {
    const { offsetX, offsetY } = getCoordinates(nativeEvent);
    contextRef.current?.beginPath();
    contextRef.current?.moveTo(offsetX, offsetY);
    setIsDrawing(true);
    setHasMark(true);
  };

  const draw = ({ nativeEvent }: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing) return;
    const { offsetX, offsetY } = getCoordinates(nativeEvent);
    contextRef.current?.lineTo(offsetX, offsetY);
    contextRef.current?.stroke();
  };

  const stopDrawing = () => {
    contextRef.current?.closePath();
    setIsDrawing(false);
  };

  const getCoordinates = (event: any) => {
    if (event.touches && event.touches[0]) {
      const rect = canvasRef.current?.getBoundingClientRect();
      return {
        offsetX: event.touches[0].clientX - (rect?.left || 0),
        offsetY: event.touches[0].clientY - (rect?.top || 0),
      };
    }
    return { offsetX: event.offsetX, offsetY: event.offsetY };
  };

  const handleReset = () => {
    const ctx = contextRef.current;
    if (ctx && canvasRef.current) {
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      ctx.globalCompositeOperation = mode === 'draw' ? 'destination-out' : 'source-over';
    }
  };

  const handleExport = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // L'image exportée aura du transparent là où on a dessiné
    const dataUrl = canvas.toDataURL('image/png');
    onSave(dataUrl);
  };

  return (
    <div className="flex flex-col items-center gap-4 py-4">
      <div className="relative border rounded-lg overflow-hidden bg-slate-200 shadow-inner" style={{ width: canvasReady ? canvasRef.current?.width : undefined }}>
        {/* Image de fond (pour voir ce qu'on dessine) */}
        <img src={imageUrl} alt="Background" className="absolute inset-0 w-full h-full object-cover pointer-events-none opacity-100" />
        
        {/* Canvas de dessin (couche de masque) */}
        <canvas
          ref={canvasRef}
          onMouseDown={startDrawing}
          onMouseMove={draw}
          onMouseUp={stopDrawing}
          onMouseLeave={stopDrawing}
          onTouchStart={startDrawing}
          onTouchMove={draw}
          onTouchEnd={stopDrawing}
          className="relative z-10 cursor-crosshair touch-none opacity-60"
        />
      </div>

      <div className="flex flex-wrap items-center justify-center gap-4 w-full max-w-md bg-white p-3 rounded-full shadow-sm border">
        <div className="flex gap-1 border-r pr-4">
          <Button 
            variant={mode === 'draw' ? 'default' : 'ghost'} 
            size="sm" 
            onClick={() => setMode('draw')}
            className="rounded-full"
          >
            <Pencil className="w-4 h-4 mr-2" /> Dessiner
          </Button>
          <Button 
            variant={mode === 'erase' ? 'default' : 'ghost'} 
            size="sm" 
            onClick={() => setMode('erase')}
            className="rounded-full"
          >
            <Eraser className="w-4 h-4 mr-2" /> Gommer
          </Button>
        </div>

        <div className="flex items-center gap-2 flex-1 min-w-[120px]">
          <span className="text-xs font-medium text-muted-foreground">Taille</span>
          <input 
            type="range" 
            min="5" max="80" 
            value={brushSize} 
            onChange={(e) => setBrushSize(parseInt(e.target.value))}
            className="flex-1"
          />
        </div>

        <Button variant="ghost" size="sm" onClick={handleReset} className="rounded-full">
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      <div className="flex gap-3 w-full max-w-md pt-2">
        <Button variant="outline" className="flex-1" onClick={onCancel}>Annuler</Button>
        <Button className="flex-1" onClick={handleExport} disabled={!canvasReady || !hasMark}>Valider le marquage</Button>
      </div>
    </div>
  );
}
