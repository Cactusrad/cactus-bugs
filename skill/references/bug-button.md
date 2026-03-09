# Composants Bug Report Button

## React Component

```tsx
// BugReportButton.tsx
import { useState, useRef, useEffect, useCallback } from 'react';

interface BugReportProps {
  apiKey: string;
  projectSlug: string;
  reporter?: string;
}

// --- Annotation Editor Sub-component ---
type Stroke = { points: {x: number; y: number}[]; color: string; width: number; isErased: boolean };
type TextAnnotation = { id: string; x: number; y: number; text: string; color: string; fontSize: number };
type AnnotationTool = 'pen' | 'text' | 'eraser';
const ANNOTATION_COLORS = ['#FF3B30', '#007AFF', '#34C759', '#FFCC00', '#FFFFFF'];

function AnnotationEditor({ imageDataUrl, onSave, onCancel }: {
  imageDataUrl: string;
  onSave: (file: File) => void;
  onCancel: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<AnnotationTool>('pen');
  const [color, setColor] = useState(ANNOTATION_COLORS[0]);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [texts, setTexts] = useState<TextAnnotation[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const currentStroke = useRef<Stroke | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Load image and set canvas size
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      setImgSize({ w: img.width, h: img.height });
    };
    img.src = imageDataUrl;
  }, [imageDataUrl]);

  // Redraw canvas whenever strokes change
  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);
    strokes.forEach(s => {
      if (s.isErased || s.points.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(s.points[0].x, s.points[0].y);
      s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
    });
  }, [strokes]);

  useEffect(() => { redraw(); }, [redraw, imgSize]);

  const getCanvasCoords = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    return {
      x: (clientX - rect.left) * (canvas.width / rect.width),
      y: (clientY - rect.top) * (canvas.height / rect.height),
    };
  };

  const handlePointerDown = (e: React.MouseEvent | React.TouchEvent) => {
    if ('touches' in e) e.preventDefault();
    if (tool === 'text') e.preventDefault(); // Prevent canvas from stealing focus from contenteditable
    const pos = getCanvasCoords(e);

    if (tool === 'pen') {
      currentStroke.current = { points: [pos], color, width: 3, isErased: false };
      setIsDrawing(true);
    } else if (tool === 'eraser') {
      // Find and erase stroke under cursor
      setStrokes(prev => {
        const updated = [...prev];
        for (let i = updated.length - 1; i >= 0; i--) {
          const s = updated[i];
          if (s.isErased) continue;
          const hit = s.points.some(p => Math.hypot(p.x - pos.x, p.y - pos.y) < 12);
          if (hit) { updated[i] = { ...s, isErased: true }; break; }
        }
        return updated;
      });
    } else if (tool === 'text') {
      const id = 'txt-' + Date.now();
      // Convert canvas coords to CSS coords for the overlay div
      const canvas = canvasRef.current!;
      const rect = canvas.getBoundingClientRect();
      const cssX = pos.x * (rect.width / canvas.width);
      const cssY = pos.y * (rect.height / canvas.height);
      setTexts(prev => [...prev, { id, x: cssX, y: cssY, text: '', color, fontSize: 16 }]);
      // Focus will be set by the contentEditable div's autoFocus
    }
  };

  const handlePointerMove = (e: React.MouseEvent | React.TouchEvent) => {
    if ('touches' in e) e.preventDefault();
    if (!isDrawing || tool !== 'pen' || !currentStroke.current) return;
    const pos = getCanvasCoords(e);
    currentStroke.current.points.push(pos);
    // Live draw current stroke
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const pts = currentStroke.current.points;
    if (pts.length >= 2) {
      ctx.beginPath();
      ctx.strokeStyle = currentStroke.current.color;
      ctx.lineWidth = currentStroke.current.width;
      ctx.lineCap = 'round';
      ctx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y);
      ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
      ctx.stroke();
    }
  };

  const handlePointerUp = () => {
    if (isDrawing && currentStroke.current && currentStroke.current.points.length >= 2) {
      setStrokes(prev => [...prev, currentStroke.current!]);
    }
    currentStroke.current = null;
    setIsDrawing(false);
  };

  const handleTextBlur = (id: string, newText: string) => {
    if (!newText.trim()) {
      // Delay removal to avoid race condition with mouseup stealing focus
      setTimeout(() => {
        setTexts(prev => prev.filter(t => t.id !== id));
      }, 200);
    } else {
      setTexts(prev => prev.map(t => t.id === id ? { ...t, text: newText } : t));
    }
  };

  const handleSave = () => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    // Create offscreen canvas at full image resolution
    const offscreen = document.createElement('canvas');
    offscreen.width = img.width;
    offscreen.height = img.height;
    const ctx = offscreen.getContext('2d')!;
    ctx.drawImage(img, 0, 0);
    // Draw strokes
    strokes.forEach(s => {
      if (s.isErased || s.points.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(s.points[0].x, s.points[0].y);
      s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
    });
    // Draw text annotations
    const displayCanvas = canvasRef.current!;
    const rect = displayCanvas.getBoundingClientRect();
    const scaleX = img.width / rect.width;
    const scaleY = img.height / rect.height;
    texts.forEach(t => {
      if (!t.text.trim()) return;
      ctx.font = `bold ${t.fontSize * scaleY}px sans-serif`;
      ctx.fillStyle = t.color;
      ctx.strokeStyle = 'rgba(0,0,0,0.6)';
      ctx.lineWidth = 3;
      ctx.strokeText(t.text, t.x * scaleX, t.y * scaleY + t.fontSize * scaleY);
      ctx.fillText(t.text, t.x * scaleX, t.y * scaleY + t.fontSize * scaleY);
    });
    offscreen.toBlob((blob) => {
      if (blob) onSave(new File([blob], 'screenshot.png', { type: 'image/png' }));
    });
  };

  const toolbarBtn = (label: string, active: boolean, onClick: () => void) => (
    <button onClick={onClick} style={{
      padding: '6px 14px', border: 'none', borderRadius: '4px', cursor: 'pointer',
      background: active ? '#007AFF' : '#555', color: 'white', fontSize: '13px', fontWeight: active ? 'bold' : 'normal',
    }}>{label}</button>
  );

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 10001, background: 'rgba(0,0,0,0.85)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px',
        background: '#1a1a1a', borderBottom: '1px solid #333', flexWrap: 'wrap',
      }}>
        {toolbarBtn('Crayon', tool === 'pen', () => setTool('pen'))}
        {toolbarBtn('Texte', tool === 'text', () => setTool('text'))}
        {toolbarBtn('Gomme', tool === 'eraser', () => setTool('eraser'))}
        <span style={{ width: '1px', height: '24px', background: '#555', margin: '0 4px' }} />
        {ANNOTATION_COLORS.map(c => (
          <button key={c} onClick={() => setColor(c)} style={{
            width: '24px', height: '24px', borderRadius: '50%', border: color === c ? '3px solid white' : '2px solid #666',
            background: c, cursor: 'pointer', padding: 0,
          }} />
        ))}
        <span style={{ flex: 1 }} />
        <button onClick={handleSave} style={{
          padding: '6px 18px', background: '#34C759', color: 'white', border: 'none',
          borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px',
        }}>Enregistrer</button>
        <button onClick={onCancel} style={{
          padding: '6px 12px', background: '#666', color: 'white', border: 'none',
          borderRadius: '4px', cursor: 'pointer', fontSize: '13px',
        }}>✕</button>
      </div>
      {/* Canvas area */}
      <div style={{ flex: 1, overflow: 'auto', display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: '20px' }}>
        {imgSize.w > 0 && (
          <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
            <canvas
              ref={canvasRef}
              width={imgSize.w}
              height={imgSize.h}
              style={{ maxWidth: '100%', maxHeight: 'calc(100vh - 100px)', display: 'block', cursor: tool === 'pen' ? 'crosshair' : tool === 'eraser' ? 'pointer' : 'text' }}
              onMouseDown={handlePointerDown}
              onMouseMove={handlePointerMove}
              onMouseUp={handlePointerUp}
              onMouseLeave={handlePointerUp}
              onTouchStart={handlePointerDown}
              onTouchMove={handlePointerMove}
              onTouchEnd={handlePointerUp}
            />
            {/* Text overlays */}
            {texts.map(t => (
              <div
                key={t.id}
                contentEditable
                suppressContentEditableWarning
                onBlur={(e) => handleTextBlur(t.id, e.currentTarget.innerText)}
                onDoubleClick={(e) => { e.currentTarget.focus(); }}
                style={{
                  position: 'absolute', left: t.x, top: t.y,
                  color: t.color, fontSize: t.fontSize, fontWeight: 'bold', fontFamily: 'sans-serif',
                  background: 'rgba(0,0,0,0.3)', padding: '2px 4px', borderRadius: '2px',
                  outline: 'none', minWidth: '20px', cursor: 'text', whiteSpace: 'pre',
                  textShadow: '1px 1px 2px rgba(0,0,0,0.8)',
                }}
                ref={(el) => { if (el && !t.text) el.focus(); }}
              >{t.text}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// --- Main Component ---
export function BugReportButton({ apiKey, projectSlug, reporter = 'anonymous' }: BugReportProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<'bug' | 'suggestion'>('bug');
  const [priority, setPriority] = useState<'basse' | 'normale' | 'haute' | 'critique'>('normale');
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [annotatorOpen, setAnnotatorOpen] = useState(false);
  const [screenshotDataUrl, setScreenshotDataUrl] = useState<string | null>(null);

  const captureScreenshot = async () => {
    try {
      const canvas = await html2canvas(document.body);
      const dataUrl = canvas.toDataURL('image/png');
      setScreenshotDataUrl(dataUrl);
      setAnnotatorOpen(true);
    } catch (e) {
      console.error('Screenshot failed:', e);
    }
  };

  const handleAnnotationSave = (file: File) => {
    setScreenshot(file);
    setAnnotatorOpen(false);
    setScreenshotDataUrl(null);
  };

  const handleAnnotationCancel = () => {
    setAnnotatorOpen(false);
    setScreenshotDataUrl(null);
  };

  const submit = async () => {
    if (!title.trim()) return;
    setLoading(true);

    try {
      // Create issue
      const res = await fetch('http://localhost:9010/api/v1/issues', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type,
          title,
          description,
          priority,
          reporter,
          metadata: {
            url: window.location.href,
            user_agent: navigator.userAgent,
          },
        }),
      });

      const issue = await res.json();

      // Upload screenshot if exists
      if (screenshot && issue.reference) {
        const formData = new FormData();
        formData.append('file', screenshot);
        await fetch(`http://localhost:9010/api/v1/issues/${issue.reference}/attachments`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${apiKey}` },
          body: formData,
        });
      }

      setSuccess(true);
      setTimeout(() => {
        setIsOpen(false);
        setSuccess(false);
        setTitle('');
        setDescription('');
        setScreenshot(null);
      }, 2000);
    } catch (e) {
      console.error('Bug report failed:', e);
    } finally {
      setLoading(false);
    }
  };

  if (annotatorOpen && screenshotDataUrl) {
    return <AnnotationEditor imageDataUrl={screenshotDataUrl} onSave={handleAnnotationSave} onCancel={handleAnnotationCancel} />;
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          background: '#dc2626',
          color: 'white',
          border: 'none',
          borderRadius: '50%',
          width: '56px',
          height: '56px',
          cursor: 'pointer',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          fontSize: '24px',
        }}
        title="Signaler un bug"
      >
        🐛
      </button>
    );
  }

  return (
    <div style={{
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      background: 'white',
      borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      padding: '20px',
      width: '360px',
      maxHeight: '80vh',
      overflow: 'auto',
      zIndex: 9999,
    }}>
      {success ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <div style={{ fontSize: '48px' }}>✅</div>
          <p>Bug signale avec succes!</p>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>Signaler un probleme</h3>
            <button onClick={() => setIsOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <select value={type} onChange={(e) => setType(e.target.value as any)} style={{ width: '100%', padding: '8px' }}>
              <option value="bug">Bug</option>
              <option value="suggestion">Suggestion</option>
              <option value="feature">Fonctionnalite</option>
            </select>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <input
              type="text"
              placeholder="Titre du probleme"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <textarea
              placeholder="Description (optionnel)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              style={{ width: '100%', padding: '8px', boxSizing: 'border-box', resize: 'vertical' }}
            />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <select value={priority} onChange={(e) => setPriority(e.target.value as any)} style={{ width: '100%', padding: '8px' }}>
              <option value="basse">Priorite basse</option>
              <option value="normale">Priorite normale</option>
              <option value="haute">Priorite haute</option>
              <option value="critique">Critique</option>
            </select>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <button onClick={captureScreenshot} style={{ marginRight: '8px', padding: '8px 12px' }}>
              📷 Capture ecran
            </button>
            {screenshot && <span style={{ color: 'green' }}>✓ Capture prete</span>}
          </div>

          <button
            onClick={submit}
            disabled={loading || !title.trim()}
            style={{
              width: '100%',
              padding: '12px',
              background: loading ? '#ccc' : '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Envoi...' : 'Envoyer le rapport'}
          </button>
        </>
      )}
    </div>
  );
}
```

**Utilisation:**
```tsx
// Ajouter html2canvas: npm install html2canvas
import { BugReportButton } from './BugReportButton';

function App() {
  return (
    <>
      {/* ... votre app ... */}
      <BugReportButton
        apiKey="PRO_xxx..."
        projectSlug="mon-projet"
        reporter="user@email.com"
      />
    </>
  );
}
```

---

## Vue Component

```vue
<!-- BugReportButton.vue -->
<template>
  <div>
    <!-- Annotation Editor (fullscreen overlay) -->
    <div v-if="annotatorOpen && screenshotDataUrl" class="annotation-overlay">
      <div class="annotation-toolbar">
        <button :class="['tool-btn', { active: annotationTool === 'pen' }]" @click="annotationTool = 'pen'">Crayon</button>
        <button :class="['tool-btn', { active: annotationTool === 'text' }]" @click="annotationTool = 'text'">Texte</button>
        <button :class="['tool-btn', { active: annotationTool === 'eraser' }]" @click="annotationTool = 'eraser'">Gomme</button>
        <span class="toolbar-sep" />
        <button v-for="c in annotationColors" :key="c" class="color-dot"
          :style="{ background: c, border: annotationColor === c ? '3px solid white' : '2px solid #666' }"
          @click="annotationColor = c" />
        <span class="toolbar-spacer" />
        <button class="save-btn" @click="saveAnnotation">Enregistrer</button>
        <button class="cancel-btn" @click="cancelAnnotation">✕</button>
      </div>
      <div class="annotation-area">
        <div ref="annotationContainer" class="annotation-container" v-if="annotationImgSize.w > 0">
          <canvas ref="annotationCanvas"
            :width="annotationImgSize.w" :height="annotationImgSize.h"
            :style="{ maxWidth: '100%', maxHeight: 'calc(100vh - 100px)', display: 'block', cursor: annotationTool === 'pen' ? 'crosshair' : annotationTool === 'eraser' ? 'pointer' : 'text' }"
            @mousedown="onAnnotationPointerDown" @mousemove="onAnnotationPointerMove"
            @mouseup="onAnnotationPointerUp" @mouseleave="onAnnotationPointerUp"
            @touchstart.prevent="onAnnotationPointerDown" @touchmove.prevent="onAnnotationPointerMove"
            @touchend="onAnnotationPointerUp" />
          <div v-for="t in annotationTexts" :key="t.id"
            contenteditable @blur="onTextBlur(t.id, $event)"
            @dblclick="($event.target as HTMLElement).focus()"
            :ref="(el) => { if (el && !t.text) (el as HTMLElement).focus(); }"
            :style="{
              position: 'absolute', left: t.x + 'px', top: t.y + 'px',
              color: t.color, fontSize: t.fontSize + 'px', fontWeight: 'bold', fontFamily: 'sans-serif',
              background: 'rgba(0,0,0,0.3)', padding: '2px 4px', borderRadius: '2px',
              outline: 'none', minWidth: '20px', cursor: 'text', whiteSpace: 'pre',
              textShadow: '1px 1px 2px rgba(0,0,0,0.8)',
            }">{{ t.text }}</div>
        </div>
      </div>
    </div>

    <!-- Floating button -->
    <button v-if="!isOpen && !annotatorOpen" @click="isOpen = true" class="bug-btn">🐛</button>

    <!-- Modal -->
    <div v-if="isOpen && !annotatorOpen" class="bug-modal">
      <div v-if="success" class="success">
        <div class="success-icon">✅</div>
        <p>Bug signale avec succes!</p>
      </div>

      <template v-else>
        <div class="header">
          <h3>Signaler un probleme</h3>
          <button @click="isOpen = false" class="close">✕</button>
        </div>

        <select v-model="type">
          <option value="bug">Bug</option>
          <option value="suggestion">Suggestion</option>
          <option value="feature">Fonctionnalite</option>
        </select>

        <input v-model="title" placeholder="Titre du probleme" />
        <textarea v-model="description" placeholder="Description (optionnel)" rows="4" />

        <select v-model="priority">
          <option value="basse">Priorite basse</option>
          <option value="normale">Priorite normale</option>
          <option value="haute">Priorite haute</option>
          <option value="critique">Critique</option>
        </select>

        <div class="screenshot-row">
          <button @click="captureScreenshot">📷 Capture ecran</button>
          <span v-if="screenshot" class="ready">✓ Capture prete</span>
        </div>

        <button @click="submit" :disabled="loading || !title.trim()" class="submit">
          {{ loading ? 'Envoi...' : 'Envoyer le rapport' }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import html2canvas from 'html2canvas';

const props = defineProps<{
  apiKey: string;
  projectSlug: string;
  reporter?: string;
}>();

const isOpen = ref(false);
const title = ref('');
const description = ref('');
const type = ref<'bug' | 'suggestion' | 'feature'>('bug');
const priority = ref<'basse' | 'normale' | 'haute' | 'critique'>('normale');
const screenshot = ref<File | null>(null);
const loading = ref(false);
const success = ref(false);

// Annotation editor state
const annotatorOpen = ref(false);
const screenshotDataUrl = ref<string | null>(null);
const annotationCanvas = ref<HTMLCanvasElement | null>(null);
const annotationContainer = ref<HTMLDivElement | null>(null);
const annotationTool = ref<'pen' | 'text' | 'eraser'>('pen');
const annotationColor = ref('#FF3B30');
const annotationColors = ['#FF3B30', '#007AFF', '#34C759', '#FFCC00', '#FFFFFF'];
const annotationStrokes = ref<{ points: {x:number;y:number}[]; color: string; width: number; isErased: boolean }[]>([]);
const annotationTexts = ref<{ id: string; x: number; y: number; text: string; color: string; fontSize: number }[]>([]);
const annotationImgSize = ref({ w: 0, h: 0 });
let annotationImg: HTMLImageElement | null = null;
let currentStroke: { points: {x:number;y:number}[]; color: string; width: number; isErased: boolean } | null = null;
let isDrawing = false;

const captureScreenshot = async () => {
  const canvas = await html2canvas(document.body);
  screenshotDataUrl.value = canvas.toDataURL('image/png');
  annotatorOpen.value = true;
  // Load image for annotation
  const img = new Image();
  img.onload = () => {
    annotationImg = img;
    annotationImgSize.value = { w: img.width, h: img.height };
    annotationStrokes.value = [];
    annotationTexts.value = [];
    nextTick(() => redrawAnnotation());
  };
  img.src = screenshotDataUrl.value;
};

const redrawAnnotation = () => {
  const canvas = annotationCanvas.value;
  if (!canvas || !annotationImg) return;
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(annotationImg, 0, 0);
  annotationStrokes.value.forEach(s => {
    if (s.isErased || s.points.length < 2) return;
    ctx.beginPath();
    ctx.strokeStyle = s.color;
    ctx.lineWidth = s.width;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.moveTo(s.points[0].x, s.points[0].y);
    s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
    ctx.stroke();
  });
};

watch(annotationStrokes, () => redrawAnnotation(), { deep: true });

const getAnnotationCoords = (e: MouseEvent | TouchEvent) => {
  const canvas = annotationCanvas.value!;
  const rect = canvas.getBoundingClientRect();
  const clientX = 'touches' in e ? (e as TouchEvent).touches[0].clientX : (e as MouseEvent).clientX;
  const clientY = 'touches' in e ? (e as TouchEvent).touches[0].clientY : (e as MouseEvent).clientY;
  return {
    x: (clientX - rect.left) * (canvas.width / rect.width),
    y: (clientY - rect.top) * (canvas.height / rect.height),
  };
};

const onAnnotationPointerDown = (e: MouseEvent | TouchEvent) => {
  if (annotationTool.value === 'text') e.preventDefault(); // Prevent canvas from stealing focus from contenteditable
  const pos = getAnnotationCoords(e);
  if (annotationTool.value === 'pen') {
    currentStroke = { points: [pos], color: annotationColor.value, width: 3, isErased: false };
    isDrawing = true;
  } else if (annotationTool.value === 'eraser') {
    const updated = [...annotationStrokes.value];
    for (let i = updated.length - 1; i >= 0; i--) {
      if (updated[i].isErased) continue;
      if (updated[i].points.some(p => Math.hypot(p.x - pos.x, p.y - pos.y) < 12)) {
        updated[i] = { ...updated[i], isErased: true };
        break;
      }
    }
    annotationStrokes.value = updated;
  } else if (annotationTool.value === 'text') {
    const canvas = annotationCanvas.value!;
    const rect = canvas.getBoundingClientRect();
    const cssX = pos.x * (rect.width / canvas.width);
    const cssY = pos.y * (rect.height / canvas.height);
    annotationTexts.value.push({ id: 'txt-' + Date.now(), x: cssX, y: cssY, text: '', color: annotationColor.value, fontSize: 16 });
  }
};

const onAnnotationPointerMove = (e: MouseEvent | TouchEvent) => {
  if (!isDrawing || annotationTool.value !== 'pen' || !currentStroke) return;
  const pos = getAnnotationCoords(e);
  currentStroke.points.push(pos);
  const canvas = annotationCanvas.value!;
  const ctx = canvas.getContext('2d')!;
  const pts = currentStroke.points;
  if (pts.length >= 2) {
    ctx.beginPath();
    ctx.strokeStyle = currentStroke.color;
    ctx.lineWidth = currentStroke.width;
    ctx.lineCap = 'round';
    ctx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y);
    ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
    ctx.stroke();
  }
};

const onAnnotationPointerUp = () => {
  if (isDrawing && currentStroke && currentStroke.points.length >= 2) {
    annotationStrokes.value = [...annotationStrokes.value, currentStroke];
  }
  currentStroke = null;
  isDrawing = false;
};

const onTextBlur = (id: string, e: Event) => {
  const el = e.target as HTMLElement;
  const text = el.innerText;
  if (!text.trim()) {
    // Delay removal to avoid race condition with mouseup stealing focus
    setTimeout(() => {
      if (!el.innerText.trim()) {
        annotationTexts.value = annotationTexts.value.filter(t => t.id !== id);
      }
    }, 200);
  } else {
    annotationTexts.value = annotationTexts.value.map(t => t.id === id ? { ...t, text } : t);
  }
};

const saveAnnotation = () => {
  if (!annotationImg) return;
  const offscreen = document.createElement('canvas');
  offscreen.width = annotationImg.width;
  offscreen.height = annotationImg.height;
  const ctx = offscreen.getContext('2d')!;
  ctx.drawImage(annotationImg, 0, 0);
  annotationStrokes.value.forEach(s => {
    if (s.isErased || s.points.length < 2) return;
    ctx.beginPath();
    ctx.strokeStyle = s.color;
    ctx.lineWidth = s.width;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.moveTo(s.points[0].x, s.points[0].y);
    s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
    ctx.stroke();
  });
  const displayCanvas = annotationCanvas.value!;
  const rect = displayCanvas.getBoundingClientRect();
  const scaleX = annotationImg.width / rect.width;
  const scaleY = annotationImg.height / rect.height;
  annotationTexts.value.forEach(t => {
    if (!t.text.trim()) return;
    ctx.font = `bold ${t.fontSize * scaleY}px sans-serif`;
    ctx.fillStyle = t.color;
    ctx.strokeStyle = 'rgba(0,0,0,0.6)';
    ctx.lineWidth = 3;
    ctx.strokeText(t.text, t.x * scaleX, t.y * scaleY + t.fontSize * scaleY);
    ctx.fillText(t.text, t.x * scaleX, t.y * scaleY + t.fontSize * scaleY);
  });
  offscreen.toBlob((blob) => {
    if (blob) {
      screenshot.value = new File([blob], 'screenshot.png', { type: 'image/png' });
      annotatorOpen.value = false;
      screenshotDataUrl.value = null;
    }
  });
};

const cancelAnnotation = () => {
  annotatorOpen.value = false;
  screenshotDataUrl.value = null;
};

const submit = async () => {
  if (!title.value.trim()) return;
  loading.value = true;

  const res = await fetch('http://localhost:9010/api/v1/issues', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${props.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      type: type.value,
      title: title.value,
      description: description.value,
      priority: priority.value,
      reporter: props.reporter || 'anonymous',
      metadata: { url: window.location.href, user_agent: navigator.userAgent },
    }),
  });

  const issue = await res.json();

  if (screenshot.value && issue.reference) {
    const formData = new FormData();
    formData.append('file', screenshot.value);
    await fetch(`http://localhost:9010/api/v1/issues/${issue.reference}/attachments`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${props.apiKey}` },
      body: formData,
    });
  }

  success.value = true;
  setTimeout(() => {
    isOpen.value = false;
    success.value = false;
    title.value = '';
    description.value = '';
    screenshot.value = null;
  }, 2000);

  loading.value = false;
};
</script>

<style scoped>
.bug-btn {
  position: fixed; bottom: 20px; right: 20px;
  background: #dc2626; color: white; border: none;
  border-radius: 50%; width: 56px; height: 56px;
  cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  font-size: 24px;
}
.bug-modal {
  position: fixed; bottom: 20px; right: 20px;
  background: white; border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
  padding: 20px; width: 360px; z-index: 9999;
}
.header { display: flex; justify-content: space-between; margin-bottom: 16px; }
.header h3 { margin: 0; }
.close { background: none; border: none; cursor: pointer; }
select, input, textarea { width: 100%; padding: 8px; margin-bottom: 12px; box-sizing: border-box; }
.screenshot-row { margin-bottom: 16px; }
.ready { color: green; margin-left: 8px; }
.submit {
  width: 100%; padding: 12px; background: #dc2626;
  color: white; border: none; border-radius: 6px; cursor: pointer;
}
.submit:disabled { background: #ccc; cursor: not-allowed; }
.success { text-align: center; padding: 40px 0; }
.success-icon { font-size: 48px; }
/* Annotation editor styles */
.annotation-overlay {
  position: fixed; inset: 0; z-index: 10001; background: rgba(0,0,0,0.85);
  display: flex; flex-direction: column;
}
.annotation-toolbar {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px;
  background: #1a1a1a; border-bottom: 1px solid #333; flex-wrap: wrap;
}
.tool-btn {
  padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer;
  background: #555; color: white; font-size: 13px;
}
.tool-btn.active { background: #007AFF; font-weight: bold; }
.toolbar-sep { width: 1px; height: 24px; background: #555; margin: 0 4px; }
.toolbar-spacer { flex: 1; }
.color-dot {
  width: 24px; height: 24px; border-radius: 50%; cursor: pointer; padding: 0;
}
.save-btn {
  padding: 6px 18px; background: #34C759; color: white; border: none;
  border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px;
}
.cancel-btn {
  padding: 6px 12px; background: #666; color: white; border: none;
  border-radius: 4px; cursor: pointer; font-size: 13px;
}
.annotation-area {
  flex: 1; overflow: auto; display: flex; justify-content: center;
  align-items: flex-start; padding: 20px;
}
.annotation-container { position: relative; display: inline-block; }
</style>
```

---

## HTML Vanilla

```html
<!-- bug-report.html - Ajouter avant </body> -->
<!-- Requis pour la capture screenshot -->
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>

<div id="bug-report-widget"></div>

<script>
(function() {
  const CONFIG = {
    apiKey: 'PRO_xxx...', // Remplacer par votre API key
    reporter: 'anonymous'
  };

  const API_URL = 'http://localhost:9010/api/v1';
  const ANNOTATION_COLORS = ['#FF3B30', '#007AFF', '#34C759', '#FFCC00', '#FFFFFF'];

  let screenshotFile = null;
  let annotationImg = null;
  let annotationStrokes = [];
  let annotationTexts = [];
  let annotationTool = 'pen';
  let annotationColor = ANNOTATION_COLORS[0];
  let currentStroke = null;
  let isDrawing = false;

  // Styles
  const style = document.createElement('style');
  style.textContent = `
    #bug-btn { position: fixed; bottom: 20px; right: 20px; background: #dc2626; color: white; border: none; border-radius: 50%; width: 56px; height: 56px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.3); font-size: 24px; z-index: 9999; }
    #bug-modal { position: fixed; bottom: 20px; right: 20px; background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); padding: 20px; width: 360px; z-index: 10000; display: none; }
    #bug-modal.open { display: block; }
    #bug-modal input, #bug-modal select, #bug-modal textarea { width: 100%; padding: 8px; margin-bottom: 12px; box-sizing: border-box; }
    #bug-modal .submit { width: 100%; padding: 12px; background: #dc2626; color: white; border: none; border-radius: 6px; cursor: pointer; }
    #bug-modal .header { display: flex; justify-content: space-between; margin-bottom: 16px; }
    #bug-modal .close { background: none; border: none; cursor: pointer; font-size: 18px; }
    #bug-annotation-overlay { position: fixed; inset: 0; z-index: 10001; background: rgba(0,0,0,0.85); display: none; flex-direction: column; }
    #bug-annotation-overlay.open { display: flex; }
    #bug-annotation-toolbar { display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: #1a1a1a; border-bottom: 1px solid #333; flex-wrap: wrap; }
    #bug-annotation-toolbar .tool-btn { padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer; background: #555; color: white; font-size: 13px; }
    #bug-annotation-toolbar .tool-btn.active { background: #007AFF; font-weight: bold; }
    #bug-annotation-toolbar .color-dot { width: 24px; height: 24px; border-radius: 50%; cursor: pointer; padding: 0; }
    #bug-annotation-toolbar .sep { width: 1px; height: 24px; background: #555; margin: 0 4px; }
    #bug-annotation-toolbar .spacer { flex: 1; }
    #bug-annotation-toolbar .save-btn { padding: 6px 18px; background: #34C759; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px; }
    #bug-annotation-toolbar .cancel-btn { padding: 6px 12px; background: #666; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
    #bug-annotation-area { flex: 1; overflow: auto; display: flex; justify-content: center; align-items: flex-start; padding: 20px; }
    #bug-annotation-container { position: relative; display: inline-block; }
    #bug-annotation-container canvas { max-width: 100%; max-height: calc(100vh - 100px); display: block; }
    .bug-text-annotation { position: absolute; font-weight: bold; font-family: sans-serif; background: rgba(0,0,0,0.3); padding: 2px 4px; border-radius: 2px; outline: none; min-width: 20px; cursor: text; white-space: pre; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }
  `;
  document.head.appendChild(style);

  // HTML
  const widget = document.getElementById('bug-report-widget');
  widget.innerHTML = `
    <button id="bug-btn">🐛</button>
    <div id="bug-modal">
      <div class="header">
        <h3>Signaler un probleme</h3>
        <button class="close" onclick="closeBugModal()">✕</button>
      </div>
      <select id="bug-type">
        <option value="bug">Bug</option>
        <option value="suggestion">Suggestion</option>
        <option value="feature">Fonctionnalite</option>
      </select>
      <input id="bug-title" placeholder="Titre du probleme" />
      <textarea id="bug-desc" placeholder="Description (optionnel)" rows="4"></textarea>
      <select id="bug-priority">
        <option value="basse">Priorite basse</option>
        <option value="normale" selected>Priorite normale</option>
        <option value="haute">Priorite haute</option>
        <option value="critique">Critique</option>
      </select>
      <div style="margin-bottom:16px">
        <button onclick="captureBugScreenshot()" style="margin-right:8px;padding:8px 12px">📷 Capture ecran</button>
        <span id="bug-screenshot-status" style="color:green;display:none">✓ Capture prete</span>
      </div>
      <button class="submit" onclick="submitBugReport()">Envoyer le rapport</button>
    </div>
    <div id="bug-annotation-overlay">
      <div id="bug-annotation-toolbar"></div>
      <div id="bug-annotation-area">
        <div id="bug-annotation-container"></div>
      </div>
    </div>
  `;

  // Build annotation toolbar
  function buildToolbar() {
    const tb = document.getElementById('bug-annotation-toolbar');
    tb.innerHTML = '';
    ['pen', 'text', 'eraser'].forEach(t => {
      const labels = { pen: 'Crayon', text: 'Texte', eraser: 'Gomme' };
      const btn = document.createElement('button');
      btn.className = 'tool-btn' + (annotationTool === t ? ' active' : '');
      btn.textContent = labels[t];
      btn.onclick = () => { annotationTool = t; buildToolbar(); updateCanvasCursor(); };
      tb.appendChild(btn);
    });
    const sep = document.createElement('span');
    sep.className = 'sep';
    tb.appendChild(sep);
    ANNOTATION_COLORS.forEach(c => {
      const dot = document.createElement('button');
      dot.className = 'color-dot';
      dot.style.background = c;
      dot.style.border = annotationColor === c ? '3px solid white' : '2px solid #666';
      dot.onclick = () => { annotationColor = c; buildToolbar(); };
      tb.appendChild(dot);
    });
    const spacer = document.createElement('span');
    spacer.className = 'spacer';
    tb.appendChild(spacer);
    const saveBtn = document.createElement('button');
    saveBtn.className = 'save-btn';
    saveBtn.textContent = 'Enregistrer';
    saveBtn.onclick = saveAnnotation;
    tb.appendChild(saveBtn);
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'cancel-btn';
    cancelBtn.textContent = '✕';
    cancelBtn.onclick = cancelAnnotation;
    tb.appendChild(cancelBtn);
  }

  function updateCanvasCursor() {
    const canvas = document.getElementById('bug-annotation-canvas');
    if (!canvas) return;
    canvas.style.cursor = annotationTool === 'pen' ? 'crosshair' : annotationTool === 'eraser' ? 'pointer' : 'text';
  }

  function redrawAnnotation() {
    const canvas = document.getElementById('bug-annotation-canvas');
    if (!canvas || !annotationImg) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(annotationImg, 0, 0);
    annotationStrokes.forEach(s => {
      if (s.isErased || s.points.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(s.points[0].x, s.points[0].y);
      s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
    });
  }

  function getAnnotationCoords(e) {
    const canvas = document.getElementById('bug-annotation-canvas');
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: (clientX - rect.left) * (canvas.width / rect.width),
      y: (clientY - rect.top) * (canvas.height / rect.height),
    };
  }

  function onAnnotationDown(e) {
    if (e.touches) e.preventDefault();
    if (annotationTool === 'text') e.preventDefault(); // Prevent canvas from stealing focus from contenteditable
    const pos = getAnnotationCoords(e);
    if (annotationTool === 'pen') {
      currentStroke = { points: [pos], color: annotationColor, width: 3, isErased: false };
      isDrawing = true;
    } else if (annotationTool === 'eraser') {
      for (let i = annotationStrokes.length - 1; i >= 0; i--) {
        if (annotationStrokes[i].isErased) continue;
        if (annotationStrokes[i].points.some(p => Math.hypot(p.x - pos.x, p.y - pos.y) < 12)) {
          annotationStrokes[i].isErased = true;
          redrawAnnotation();
          break;
        }
      }
    } else if (annotationTool === 'text') {
      const canvas = document.getElementById('bug-annotation-canvas');
      const rect = canvas.getBoundingClientRect();
      const cssX = pos.x * (rect.width / canvas.width);
      const cssY = pos.y * (rect.height / canvas.height);
      const id = 'txt-' + Date.now();
      const t = { id, x: cssX, y: cssY, text: '', color: annotationColor, fontSize: 16 };
      annotationTexts.push(t);
      createTextDiv(t);
    }
  }

  function onAnnotationMove(e) {
    if (e.touches) e.preventDefault();
    if (!isDrawing || annotationTool !== 'pen' || !currentStroke) return;
    const pos = getAnnotationCoords(e);
    currentStroke.points.push(pos);
    const canvas = document.getElementById('bug-annotation-canvas');
    const ctx = canvas.getContext('2d');
    const pts = currentStroke.points;
    if (pts.length >= 2) {
      ctx.beginPath();
      ctx.strokeStyle = currentStroke.color;
      ctx.lineWidth = currentStroke.width;
      ctx.lineCap = 'round';
      ctx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y);
      ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
      ctx.stroke();
    }
  }

  function onAnnotationUp() {
    if (isDrawing && currentStroke && currentStroke.points.length >= 2) {
      annotationStrokes.push(currentStroke);
    }
    currentStroke = null;
    isDrawing = false;
  }

  function createTextDiv(t) {
    const container = document.getElementById('bug-annotation-container');
    const div = document.createElement('div');
    div.className = 'bug-text-annotation';
    div.contentEditable = 'true';
    div.style.left = t.x + 'px';
    div.style.top = t.y + 'px';
    div.style.color = t.color;
    div.style.fontSize = t.fontSize + 'px';
    div.dataset.id = t.id;
    div.textContent = t.text;
    div.addEventListener('blur', function() {
      const el = this;
      const text = el.innerText;
      if (!text.trim()) {
        // Delay removal to avoid race condition with mouseup stealing focus
        setTimeout(function() {
          if (!el.innerText.trim()) {
            const idx = annotationTexts.findIndex(at => at.id === t.id);
            if (idx !== -1) annotationTexts.splice(idx, 1);
            el.remove();
          }
        }, 200);
      } else {
        const idx = annotationTexts.findIndex(at => at.id === t.id);
        if (idx !== -1) annotationTexts[idx].text = text;
      }
    });
    div.addEventListener('dblclick', function() { this.focus(); });
    container.appendChild(div);
    div.focus();
  }

  function saveAnnotation() {
    if (!annotationImg) return;
    const offscreen = document.createElement('canvas');
    offscreen.width = annotationImg.width;
    offscreen.height = annotationImg.height;
    const ctx = offscreen.getContext('2d');
    ctx.drawImage(annotationImg, 0, 0);
    annotationStrokes.forEach(s => {
      if (s.isErased || s.points.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(s.points[0].x, s.points[0].y);
      s.points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
    });
    const displayCanvas = document.getElementById('bug-annotation-canvas');
    const rect = displayCanvas.getBoundingClientRect();
    const scaleX = annotationImg.width / rect.width;
    const scaleY = annotationImg.height / rect.height;
    annotationTexts.forEach(t => {
      if (!t.text.trim()) return;
      ctx.font = `bold ${t.fontSize * scaleY}px sans-serif`;
      ctx.fillStyle = t.color;
      ctx.strokeStyle = 'rgba(0,0,0,0.6)';
      ctx.lineWidth = 3;
      ctx.strokeText(t.text, t.x * scaleX, t.y * scaleY + t.fontSize * scaleY);
      ctx.fillText(t.text, t.x * scaleX, t.y * scaleY + t.fontSize * scaleY);
    });
    offscreen.toBlob(function(blob) {
      if (blob) {
        screenshotFile = new File([blob], 'screenshot.png', { type: 'image/png' });
        document.getElementById('bug-screenshot-status').style.display = 'inline';
        cancelAnnotation();
      }
    });
  }

  function cancelAnnotation() {
    document.getElementById('bug-annotation-overlay').classList.remove('open');
    annotationStrokes = [];
    annotationTexts = [];
    annotationImg = null;
  }

  window.captureBugScreenshot = async function() {
    try {
      const canvas = await html2canvas(document.body);
      const dataUrl = canvas.toDataURL('image/png');
      // Open annotation editor
      annotationStrokes = [];
      annotationTexts = [];
      annotationTool = 'pen';
      annotationColor = ANNOTATION_COLORS[0];
      const img = new Image();
      img.onload = function() {
        annotationImg = img;
        const container = document.getElementById('bug-annotation-container');
        container.innerHTML = '<canvas id="bug-annotation-canvas"></canvas>';
        const c = document.getElementById('bug-annotation-canvas');
        c.width = img.width;
        c.height = img.height;
        updateCanvasCursor();
        c.addEventListener('mousedown', onAnnotationDown);
        c.addEventListener('mousemove', onAnnotationMove);
        c.addEventListener('mouseup', onAnnotationUp);
        c.addEventListener('mouseleave', onAnnotationUp);
        c.addEventListener('touchstart', onAnnotationDown, { passive: false });
        c.addEventListener('touchmove', onAnnotationMove, { passive: false });
        c.addEventListener('touchend', onAnnotationUp);
        redrawAnnotation();
        buildToolbar();
        document.getElementById('bug-annotation-overlay').classList.add('open');
      };
      img.src = dataUrl;
    } catch (e) {
      console.error('Screenshot failed:', e);
    }
  };

  document.getElementById('bug-btn').onclick = () => {
    document.getElementById('bug-modal').classList.add('open');
    document.getElementById('bug-btn').style.display = 'none';
  };

  window.closeBugModal = () => {
    document.getElementById('bug-modal').classList.remove('open');
    document.getElementById('bug-btn').style.display = 'block';
  };

  window.submitBugReport = async () => {
    const title = document.getElementById('bug-title').value;
    if (!title.trim()) return alert('Titre requis');

    const res = await fetch(API_URL + '/issues', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + CONFIG.apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: document.getElementById('bug-type').value,
        title: title,
        description: document.getElementById('bug-desc').value,
        priority: document.getElementById('bug-priority').value,
        reporter: CONFIG.reporter,
        metadata: { url: window.location.href, user_agent: navigator.userAgent }
      }),
    });

    if (res.ok) {
      const issue = await res.json();
      // Upload screenshot if captured
      if (screenshotFile && issue.reference) {
        const formData = new FormData();
        formData.append('file', screenshotFile);
        await fetch(API_URL + '/issues/' + issue.reference + '/attachments', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + CONFIG.apiKey },
          body: formData,
        });
      }
      alert('Bug signale avec succes!');
      closeBugModal();
      document.getElementById('bug-title').value = '';
      document.getElementById('bug-desc').value = '';
      screenshotFile = null;
      document.getElementById('bug-screenshot-status').style.display = 'none';
    }
  };
})();
</script>
```
