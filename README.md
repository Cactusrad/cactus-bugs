# Cactus Bugs - Self-Hosted Bug Tracker

A lightweight, self-hosted bug tracking service with a REST API, a web dashboard, and a **Claude Code skill** for AI-assisted bug management.

Built with FastAPI + SQLite + nginx. Ships as Docker containers. Zero external dependencies.

```
Your App                        Bugs Service (Docker)
+------------------+            +-------------------+
| Floating Bug     |  REST API  |  FastAPI backend   |
| Report Button  --------->     |  SQLite database   |
| (React/Vue/HTML) |            |  File attachments  |
+------------------+            +-------------------+
                                        |
Claude Code                             |
+------------------+    /bugs skill     |
| "Show me open  ---------------------->|
|  bugs for       |    curl API calls   |
|  my-project"    |<-----------------------
+------------------+
```

## Features

- Multi-project support with per-project API keys
- Issue types: Bug, Suggestion, Feature, Improvement
- Auto-generated references: `BUG-001`, `SUG-002`, `FEAT-003`, `IMP-004`
- Status workflow: `nouveau` -> `en_cours` -> `a_approuver` -> `termine` / `rejete`
- File attachments with auto-thumbnail generation (images)
- Full audit history on every change
- Webhook notifications on issue creation
- Built-in web dashboard (SPA)
- Claude Code skill for AI-assisted bug management
- Drop-in floating bug report button (React, Vue, vanilla HTML)
- CI/CD pipeline (GitHub Actions)

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/Cactusrad/cactus-bugs.git
cd cactus-bugs

# Generate your admin master key
cp .env.example .env
echo "ADMIN_MASTER_KEY=$(openssl rand -hex 32)" > .env
```

### 2. Start with Docker

```bash
docker compose up -d
```

The service starts on **port 9010**:
- Web dashboard: `http://localhost:9010`
- API: `http://localhost:9010/api/v1/`
- Health check: `http://localhost:9010/health`

### 3. Create your first project

```bash
# Read your admin key
export ADMIN_KEY=$(grep ADMIN_MASTER_KEY .env | cut -d= -f2)

# Create a project (the API key is shown only once!)
curl -X POST "http://localhost:9010/api/v1/admin/projects" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "slug": "my-app"}'
```

Save the returned `api_key` — it's your project's authentication token.

### 4. Create your first bug

```bash
export API_KEY="the_key_from_step_3"

curl -X POST "http://localhost:9010/api/v1/issues" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "bug",
    "title": "Login button does not respond",
    "description": "Clicking the login button on /auth does nothing. Console shows CORS error.",
    "priority": "haute",
    "reporter": "Pierre"
  }'
```

---

## Floating Bug Report Button

The killer feature: a **floating button** that your users click to report bugs directly from your app. It captures the page URL, browser info, and optional screenshots — all sent to your Bugs Service automatically.

### How It Works

```
User clicks bug button -> Modal opens -> User fills title + description
                                      -> Optional: capture screenshot
                                            |
                                            v
                                     Annotate screenshot (fullscreen editor)
                                     Draw, add text, erase, pick colors
                                     Save -> flattened PNG replaces screenshot
                                            |
                                            v
                                      -> Submit
                                            |
                                            v
                                     POST /api/v1/issues
                                     (with context_data: URL, user_agent)
                                            |
                                            v
                                     If screenshot captured:
                                     POST /api/v1/issues/{ref}/attachments
                                            |
                                            v
                                     Issue created! (BUG-042)
                                     Webhook sent (if configured)
```

### React

```bash
npm install html2canvas  # For screenshot capture
```

```tsx
// BugReportButton.tsx
import { useState, useRef, useEffect, useCallback } from 'react';

interface BugReportProps {
  apiUrl: string;       // Your bugs service URL (e.g. "http://localhost:9010")
  apiKey: string;       // Project API key
  projectSlug: string;  // Project identifier
  reporter?: string;    // Pre-fill reporter name
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
      const canvas = canvasRef.current!;
      const rect = canvas.getBoundingClientRect();
      const cssX = pos.x * (rect.width / canvas.width);
      const cssY = pos.y * (rect.height / canvas.height);
      setTexts(prev => [...prev, { id, x: cssX, y: cssY, text: '', color, fontSize: 16 }]);
    }
  };

  const handlePointerMove = (e: React.MouseEvent | React.TouchEvent) => {
    if ('touches' in e) e.preventDefault();
    if (!isDrawing || tool !== 'pen' || !currentStroke.current) return;
    const pos = getCanvasCoords(e);
    currentStroke.current.points.push(pos);
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
    const offscreen = document.createElement('canvas');
    offscreen.width = img.width;
    offscreen.height = img.height;
    const ctx = offscreen.getContext('2d')!;
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
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px',
        background: '#1a1a1a', borderBottom: '1px solid #333', flexWrap: 'wrap',
      }}>
        {toolbarBtn('Pen', tool === 'pen', () => setTool('pen'))}
        {toolbarBtn('Text', tool === 'text', () => setTool('text'))}
        {toolbarBtn('Eraser', tool === 'eraser', () => setTool('eraser'))}
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
        }}>Save</button>
        <button onClick={onCancel} style={{
          padding: '6px 12px', background: '#666', color: 'white', border: 'none',
          borderRadius: '4px', cursor: 'pointer', fontSize: '13px',
        }}>X</button>
      </div>
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
export function BugReportButton({ apiUrl, apiKey, projectSlug, reporter = 'anonymous' }: BugReportProps) {
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
      const html2canvas = (await import('html2canvas')).default;
      const canvas = await html2canvas(document.body);
      setScreenshotDataUrl(canvas.toDataURL('image/png'));
      setAnnotatorOpen(true);
    } catch (e) {
      console.error('Screenshot capture failed:', e);
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
      // 1. Create the issue
      const res = await fetch(`${apiUrl}/api/v1/issues`, {
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
          context_data: {
            url: window.location.href,
            user_agent: navigator.userAgent,
          },
        }),
      });

      const issue = await res.json();

      // 2. Upload screenshot if captured
      if (screenshot && issue.reference) {
        const formData = new FormData();
        formData.append('file', screenshot);
        await fetch(`${apiUrl}/api/v1/issues/${issue.reference}/attachments`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${apiKey}` },
          body: formData,
        });
      }

      // 3. Show success feedback
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

  // Show annotation editor fullscreen
  if (annotatorOpen && screenshotDataUrl) {
    return <AnnotationEditor imageDataUrl={screenshotDataUrl} onSave={handleAnnotationSave} onCancel={handleAnnotationCancel} />;
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed', bottom: '20px', right: '20px',
          background: '#dc2626', color: 'white', border: 'none',
          borderRadius: '50%', width: '56px', height: '56px',
          cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          fontSize: '24px', zIndex: 9999,
        }}
        title="Report a bug"
      >
        Bug
      </button>
    );
  }

  return (
    <div style={{
      position: 'fixed', bottom: '20px', right: '20px',
      background: 'white', borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      padding: '20px', width: '360px', maxHeight: '80vh',
      overflow: 'auto', zIndex: 9999,
    }}>
      {success ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <p style={{ fontSize: '18px', fontWeight: 'bold' }}>Bug reported!</p>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>Report a problem</h3>
            <button onClick={() => setIsOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px' }}>X</button>
          </div>

          <select value={type} onChange={(e) => setType(e.target.value as any)}
            style={{ width: '100%', padding: '8px', marginBottom: '12px' }}>
            <option value="bug">Bug</option>
            <option value="suggestion">Suggestion</option>
            <option value="feature">Feature request</option>
          </select>

          <input type="text" placeholder="Problem title" value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{ width: '100%', padding: '8px', marginBottom: '12px', boxSizing: 'border-box' }}
          />

          <textarea placeholder="Description (optional)" value={description}
            onChange={(e) => setDescription(e.target.value)} rows={4}
            style={{ width: '100%', padding: '8px', marginBottom: '12px', boxSizing: 'border-box', resize: 'vertical' }}
          />

          <select value={priority} onChange={(e) => setPriority(e.target.value as any)}
            style={{ width: '100%', padding: '8px', marginBottom: '12px' }}>
            <option value="basse">Low priority</option>
            <option value="normale">Normal priority</option>
            <option value="haute">High priority</option>
            <option value="critique">Critical</option>
          </select>

          <div style={{ marginBottom: '16px' }}>
            <button onClick={captureScreenshot} style={{ marginRight: '8px', padding: '8px 12px' }}>
              Capture screenshot
            </button>
            {screenshot && <span style={{ color: 'green' }}>Ready</span>}
          </div>

          <button onClick={submit} disabled={loading || !title.trim()}
            style={{
              width: '100%', padding: '12px',
              background: loading ? '#ccc' : '#dc2626',
              color: 'white', border: 'none', borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}>
            {loading ? 'Sending...' : 'Send report'}
          </button>
        </>
      )}
    </div>
  );
}
```

**Usage in your app:**

```tsx
import { BugReportButton } from './BugReportButton';

function App() {
  return (
    <>
      {/* Your app content */}
      <BugReportButton
        apiUrl="http://localhost:9010"
        apiKey="YOUR_PROJECT_API_KEY"
        projectSlug="my-app"
        reporter="user@email.com"
      />
    </>
  );
}
```

### Vue

```vue
<template>
  <div>
    <!-- Annotation Editor (fullscreen overlay) -->
    <div v-if="annotatorOpen && screenshotDataUrl" class="annotation-overlay">
      <div class="annotation-toolbar">
        <button :class="['tool-btn', { active: annotationTool === 'pen' }]" @click="annotationTool = 'pen'">Pen</button>
        <button :class="['tool-btn', { active: annotationTool === 'text' }]" @click="annotationTool = 'text'">Text</button>
        <button :class="['tool-btn', { active: annotationTool === 'eraser' }]" @click="annotationTool = 'eraser'">Eraser</button>
        <span class="toolbar-sep" />
        <button v-for="c in annotationColors" :key="c" class="color-dot"
          :style="{ background: c, border: annotationColor === c ? '3px solid white' : '2px solid #666' }"
          @click="annotationColor = c" />
        <span class="toolbar-spacer" />
        <button class="save-btn" @click="saveAnnotation">Save</button>
        <button class="cancel-btn" @click="cancelAnnotation">X</button>
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

    <button v-if="!isOpen && !annotatorOpen" @click="isOpen = true" class="bug-btn">Bug</button>

    <div v-if="isOpen && !annotatorOpen" class="bug-modal">
      <div v-if="success" class="success">
        <p>Bug reported!</p>
      </div>
      <template v-else>
        <div class="header">
          <h3>Report a problem</h3>
          <button @click="isOpen = false" class="close">X</button>
        </div>
        <select v-model="type">
          <option value="bug">Bug</option>
          <option value="suggestion">Suggestion</option>
          <option value="feature">Feature request</option>
        </select>
        <input v-model="title" placeholder="Problem title" />
        <textarea v-model="description" placeholder="Description (optional)" rows="4" />
        <select v-model="priority">
          <option value="basse">Low</option>
          <option value="normale">Normal</option>
          <option value="haute">High</option>
          <option value="critique">Critical</option>
        </select>
        <div class="screenshot-row">
          <button @click="captureScreenshot">Capture screenshot</button>
          <span v-if="screenshot" class="ready">Ready</span>
        </div>
        <button @click="submit" :disabled="loading || !title.trim()" class="submit">
          {{ loading ? 'Sending...' : 'Send report' }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

const props = defineProps<{
  apiUrl: string;
  apiKey: string;
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
  const html2canvas = (await import('html2canvas')).default;
  const canvas = await html2canvas(document.body);
  screenshotDataUrl.value = canvas.toDataURL('image/png');
  annotatorOpen.value = true;
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
    ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
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
        updated[i] = { ...updated[i], isErased: true }; break;
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
    ctx.strokeStyle = currentStroke.color; ctx.lineWidth = currentStroke.width; ctx.lineCap = 'round';
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
    ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
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
    ctx.fillStyle = t.color; ctx.strokeStyle = 'rgba(0,0,0,0.6)'; ctx.lineWidth = 3;
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

  const res = await fetch(`${props.apiUrl}/api/v1/issues`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${props.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      type: type.value, title: title.value, description: description.value,
      priority: priority.value, reporter: props.reporter || 'anonymous',
      context_data: { url: window.location.href, user_agent: navigator.userAgent },
    }),
  });
  const issue = await res.json();

  if (screenshot.value && issue.reference) {
    const fd = new FormData();
    fd.append('file', screenshot.value);
    await fetch(`${props.apiUrl}/api/v1/issues/${issue.reference}/attachments`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${props.apiKey}` },
      body: fd,
    });
  }

  success.value = true;
  setTimeout(() => {
    isOpen.value = false; success.value = false;
    title.value = ''; description.value = ''; screenshot.value = null;
  }, 2000);
  loading.value = false;
};
</script>
```

**Usage:**

```vue
<BugReportButton api-url="http://localhost:9010" api-key="YOUR_KEY" reporter="user@email.com" />
```

### Vanilla HTML

Drop this snippet before `</body>` in any HTML page:

```html
<!-- Required for screenshot capture -->
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>

<div id="bug-report-widget"></div>
<script>
(function() {
  // CONFIGURE THESE
  const BUGS_API_URL = 'http://localhost:9010';
  const API_KEY = 'YOUR_PROJECT_API_KEY';
  const REPORTER = 'anonymous';
  const ANNOTATION_COLORS = ['#FF3B30', '#007AFF', '#34C759', '#FFCC00', '#FFFFFF'];

  let screenshotFile = null;
  let annotationImg = null;
  let annotationStrokes = [];
  let annotationTexts = [];
  let annotationTool = 'pen';
  let annotationColor = ANNOTATION_COLORS[0];
  let currentStroke = null;
  let isDrawing = false;

  const style = document.createElement('style');
  style.textContent = `
    #bug-btn { position:fixed; bottom:20px; right:20px; background:#dc2626; color:white;
      border:none; border-radius:50%; width:56px; height:56px; cursor:pointer;
      box-shadow:0 4px 12px rgba(0,0,0,.3); font-size:14px; font-weight:bold; z-index:9999; }
    #bug-modal { position:fixed; bottom:20px; right:20px; background:white; border-radius:12px;
      box-shadow:0 8px 32px rgba(0,0,0,.2); padding:20px; width:360px; z-index:10000; display:none; }
    #bug-modal.open { display:block; }
    #bug-modal input, #bug-modal select, #bug-modal textarea {
      width:100%; padding:8px; margin-bottom:12px; box-sizing:border-box; }
    #bug-modal .submit { width:100%; padding:12px; background:#dc2626; color:white;
      border:none; border-radius:6px; cursor:pointer; }
    #bug-modal .header { display:flex; justify-content:space-between; margin-bottom:16px; }
    #bug-modal .close { background:none; border:none; cursor:pointer; font-size:18px; }
    #bug-annotation-overlay { position:fixed; inset:0; z-index:10001; background:rgba(0,0,0,0.85); display:none; flex-direction:column; }
    #bug-annotation-overlay.open { display:flex; }
    #bug-annotation-toolbar { display:flex; align-items:center; gap:8px; padding:10px 16px; background:#1a1a1a; border-bottom:1px solid #333; flex-wrap:wrap; }
    #bug-annotation-toolbar .tool-btn { padding:6px 14px; border:none; border-radius:4px; cursor:pointer; background:#555; color:white; font-size:13px; }
    #bug-annotation-toolbar .tool-btn.active { background:#007AFF; font-weight:bold; }
    #bug-annotation-toolbar .color-dot { width:24px; height:24px; border-radius:50%; cursor:pointer; padding:0; }
    #bug-annotation-toolbar .sep { width:1px; height:24px; background:#555; margin:0 4px; }
    #bug-annotation-toolbar .spacer { flex:1; }
    #bug-annotation-toolbar .save-btn { padding:6px 18px; background:#34C759; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold; font-size:13px; }
    #bug-annotation-toolbar .cancel-btn { padding:6px 12px; background:#666; color:white; border:none; border-radius:4px; cursor:pointer; font-size:13px; }
    #bug-annotation-area { flex:1; overflow:auto; display:flex; justify-content:center; align-items:flex-start; padding:20px; }
    #bug-annotation-container { position:relative; display:inline-block; }
    #bug-annotation-container canvas { max-width:100%; max-height:calc(100vh - 100px); display:block; }
    .bug-text-annotation { position:absolute; font-weight:bold; font-family:sans-serif; background:rgba(0,0,0,0.3); padding:2px 4px; border-radius:2px; outline:none; min-width:20px; cursor:text; white-space:pre; text-shadow:1px 1px 2px rgba(0,0,0,0.8); }
  `;
  document.head.appendChild(style);

  document.getElementById('bug-report-widget').innerHTML = `
    <button id="bug-btn">Bug</button>
    <div id="bug-modal">
      <div class="header">
        <h3 style="margin:0">Report a problem</h3>
        <button class="close" onclick="closeBugModal()">X</button>
      </div>
      <select id="bug-type">
        <option value="bug">Bug</option>
        <option value="suggestion">Suggestion</option>
        <option value="feature">Feature request</option>
      </select>
      <input id="bug-title" placeholder="Problem title" />
      <textarea id="bug-desc" placeholder="Description (optional)" rows="4"></textarea>
      <select id="bug-priority">
        <option value="basse">Low</option>
        <option value="normale" selected>Normal</option>
        <option value="haute">High</option>
        <option value="critique">Critical</option>
      </select>
      <div style="margin-bottom:16px">
        <button onclick="captureBugScreenshot()" style="margin-right:8px;padding:8px 12px">Capture screenshot</button>
        <span id="bug-screenshot-status" style="color:green;display:none">Ready</span>
      </div>
      <button class="submit" onclick="submitBugReport()">Send report</button>
    </div>
    <div id="bug-annotation-overlay">
      <div id="bug-annotation-toolbar"></div>
      <div id="bug-annotation-area">
        <div id="bug-annotation-container"></div>
      </div>
    </div>
  `;

  function buildToolbar() {
    const tb = document.getElementById('bug-annotation-toolbar');
    tb.innerHTML = '';
    ['pen', 'text', 'eraser'].forEach(t => {
      const labels = { pen: 'Pen', text: 'Text', eraser: 'Eraser' };
      const btn = document.createElement('button');
      btn.className = 'tool-btn' + (annotationTool === t ? ' active' : '');
      btn.textContent = labels[t];
      btn.onclick = () => { annotationTool = t; buildToolbar(); updateCanvasCursor(); };
      tb.appendChild(btn);
    });
    const sep = document.createElement('span'); sep.className = 'sep'; tb.appendChild(sep);
    ANNOTATION_COLORS.forEach(c => {
      const dot = document.createElement('button');
      dot.className = 'color-dot'; dot.style.background = c;
      dot.style.border = annotationColor === c ? '3px solid white' : '2px solid #666';
      dot.onclick = () => { annotationColor = c; buildToolbar(); };
      tb.appendChild(dot);
    });
    const spacer = document.createElement('span'); spacer.className = 'spacer'; tb.appendChild(spacer);
    const saveBtn = document.createElement('button');
    saveBtn.className = 'save-btn'; saveBtn.textContent = 'Save'; saveBtn.onclick = saveAnnotation;
    tb.appendChild(saveBtn);
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'cancel-btn'; cancelBtn.textContent = 'X'; cancelBtn.onclick = cancelAnnotation;
    tb.appendChild(cancelBtn);
  }

  function updateCanvasCursor() {
    const canvas = document.getElementById('bug-annotation-canvas');
    if (canvas) canvas.style.cursor = annotationTool === 'pen' ? 'crosshair' : annotationTool === 'eraser' ? 'pointer' : 'text';
  }

  function redrawAnnotation() {
    const canvas = document.getElementById('bug-annotation-canvas');
    if (!canvas || !annotationImg) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(annotationImg, 0, 0);
    annotationStrokes.forEach(s => {
      if (s.isErased || s.points.length < 2) return;
      ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
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
          annotationStrokes[i].isErased = true; redrawAnnotation(); break;
        }
      }
    } else if (annotationTool === 'text') {
      const canvas = document.getElementById('bug-annotation-canvas');
      const rect = canvas.getBoundingClientRect();
      const cssX = pos.x * (rect.width / canvas.width);
      const cssY = pos.y * (rect.height / canvas.height);
      const id = 'txt-' + Date.now();
      annotationTexts.push({ id, x: cssX, y: cssY, text: '', color: annotationColor, fontSize: 16 });
      createTextDiv(annotationTexts[annotationTexts.length - 1]);
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
      ctx.beginPath(); ctx.strokeStyle = currentStroke.color; ctx.lineWidth = currentStroke.width; ctx.lineCap = 'round';
      ctx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y);
      ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y);
      ctx.stroke();
    }
  }

  function onAnnotationUp() {
    if (isDrawing && currentStroke && currentStroke.points.length >= 2) annotationStrokes.push(currentStroke);
    currentStroke = null; isDrawing = false;
  }

  function createTextDiv(t) {
    const container = document.getElementById('bug-annotation-container');
    const div = document.createElement('div');
    div.className = 'bug-text-annotation';
    div.contentEditable = 'true';
    div.style.left = t.x + 'px'; div.style.top = t.y + 'px';
    div.style.color = t.color; div.style.fontSize = t.fontSize + 'px';
    div.dataset.id = t.id; div.textContent = t.text;
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
    container.appendChild(div); div.focus();
  }

  function saveAnnotation() {
    if (!annotationImg) return;
    const offscreen = document.createElement('canvas');
    offscreen.width = annotationImg.width; offscreen.height = annotationImg.height;
    const ctx = offscreen.getContext('2d');
    ctx.drawImage(annotationImg, 0, 0);
    annotationStrokes.forEach(s => {
      if (s.isErased || s.points.length < 2) return;
      ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
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
      ctx.fillStyle = t.color; ctx.strokeStyle = 'rgba(0,0,0,0.6)'; ctx.lineWidth = 3;
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
    annotationStrokes = []; annotationTexts = []; annotationImg = null;
  }

  window.captureBugScreenshot = async function() {
    try {
      const canvas = await html2canvas(document.body);
      const dataUrl = canvas.toDataURL('image/png');
      annotationStrokes = []; annotationTexts = [];
      annotationTool = 'pen'; annotationColor = ANNOTATION_COLORS[0];
      const img = new Image();
      img.onload = function() {
        annotationImg = img;
        const container = document.getElementById('bug-annotation-container');
        container.innerHTML = '<canvas id="bug-annotation-canvas"></canvas>';
        const c = document.getElementById('bug-annotation-canvas');
        c.width = img.width; c.height = img.height;
        updateCanvasCursor();
        c.addEventListener('mousedown', onAnnotationDown);
        c.addEventListener('mousemove', onAnnotationMove);
        c.addEventListener('mouseup', onAnnotationUp);
        c.addEventListener('mouseleave', onAnnotationUp);
        c.addEventListener('touchstart', onAnnotationDown, { passive: false });
        c.addEventListener('touchmove', onAnnotationMove, { passive: false });
        c.addEventListener('touchend', onAnnotationUp);
        redrawAnnotation(); buildToolbar();
        document.getElementById('bug-annotation-overlay').classList.add('open');
      };
      img.src = dataUrl;
    } catch (e) { console.error('Screenshot failed:', e); }
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
    if (!title.trim()) return alert('Title required');

    const res = await fetch(BUGS_API_URL + '/api/v1/issues', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + API_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: document.getElementById('bug-type').value,
        title: title,
        description: document.getElementById('bug-desc').value,
        priority: document.getElementById('bug-priority').value,
        reporter: REPORTER,
        context_data: { url: window.location.href, user_agent: navigator.userAgent }
      }),
    });

    if (res.ok) {
      const issue = await res.json();
      if (screenshotFile && issue.reference) {
        const formData = new FormData();
        formData.append('file', screenshotFile);
        await fetch(BUGS_API_URL + '/api/v1/issues/' + issue.reference + '/attachments', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + API_KEY },
          body: formData,
        });
      }
      alert('Bug reported!');
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

### Button Configuration

| Prop / Variable | Required | Description |
|-----------------|----------|-------------|
| `apiUrl` | Yes | URL of your bugs service (e.g. `http://localhost:9010`) |
| `apiKey` | Yes | Project API key (from project creation) |
| `projectSlug` | No | Project slug (for display/routing) |
| `reporter` | No | Pre-filled reporter name/email (default: `anonymous`) |

### What Gets Captured Automatically

The button automatically sends `context_data` with every report:

```json
{
  "url": "http://myapp.com/dashboard?tab=settings",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
}
```

This helps developers reproduce bugs by knowing exactly where the user was.

### Screenshot Capture & Annotation

All three components (React, Vue, vanilla HTML) include screenshot capture via `html2canvas` with a built-in **annotation editor**. When the user clicks "Capture screenshot":

1. `html2canvas` renders the current DOM to a canvas
2. A **fullscreen annotation editor** opens with the captured image
3. The user can annotate the screenshot using:
   - **Pen tool** — free-draw on the image (3px stroke, `lineCap: round`)
   - **Text tool** — click to place editable text labels (`contenteditable` divs)
   - **Eraser tool** — click on a stroke to remove it entirely (not white paint)
   - **5 colors** — Red `#FF3B30`, Blue `#007AFF`, Green `#34C759`, Yellow `#FFCC00`, White `#FFFFFF`
4. Double-click on existing text to re-edit it
5. Click **Save** to flatten everything (image + strokes + text) into a final PNG
6. The annotated PNG replaces the original screenshot — no further editing possible
7. After issue creation, the PNG is uploaded as an attachment via `POST /api/v1/issues/{ref}/attachments`
8. The screenshot appears in the issue detail view with auto-generated thumbnail

The annotation editor uses a hybrid Canvas + HTML approach: strokes are drawn on a `<canvas>`, while text annotations are `contenteditable` divs positioned over the canvas for native text editing. Touch events (`touchstart`/`touchmove`/`touchend`) are supported for mobile/tablet use.

**Note:** `html2canvas` does not capture cross-origin images, WebGL canvases, or iframes. For those cases, consider using the browser's native `navigator.mediaDevices.getDisplayMedia()` API.

---

## Claude Code Skill Integration

This repo includes a **Claude Code skill** (`/bugs`) that lets Claude manage bugs via natural language.

### What Claude Can Do With This Skill

When you type `/bugs` or mention "bugs" in Claude Code, Claude can:

- **List open bugs:** "Show me all open bugs for my-project"
- **Create a bug:** "Create a high-priority bug: the login page crashes on Safari"
- **Update status:** "Mark BUG-042 as en_cours and assign to Pierre"
- **Add comments:** "Add a comment to BUG-042: Fixed in commit abc123"
- **View details:** "Show me the full history of BUG-042"
- **Check stats:** "How many open bugs do we have?"
- **Add the floating button:** "Add a bug report button to my React app"

### How It Works

```
You: "show me open bugs"
                |
                v
Claude Code loads /bugs skill
                |
                v
Reads SKILL.md -> understands API endpoints + auth
                |
                v
Finds API_KEY in your project's .env or CLAUDE.md
                |
                v
Runs: curl -s "http://localhost:9010/api/v1/issues?status=nouveau,en_cours" \
        -H "Authorization: Bearer $API_KEY" | jq
                |
                v
Formats and displays the results to you
```

### Installing the Skill

```bash
# Copy the skill directory to your Claude Code skills folder
cp -r skill/  ~/.claude/skills/bugs/
```

That's it. Claude Code auto-discovers skills in `~/.claude/skills/`. Next time you type `/bugs`, the skill activates.

### Skill File Structure

```
~/.claude/skills/bugs/
  SKILL.md                      # Main skill definition (loaded by Claude)
  references/
    api-reference.md            # Full API docs (loaded on demand)
    bug-button.md               # Button component code (loaded on demand)
```

### Configuring the Skill for Your Instance

Edit `~/.claude/skills/bugs/SKILL.md` and update the API Base URL to point to your instance:

```markdown
**API Base URL:** `http://your-server:9010`
```

Or better: set `BUGS_SERVICE_URL` and `BUGS_SERVICE_API_KEY` in your project's `.env` file. Claude will read them from there.

### Skill Metadata

The skill is defined by YAML frontmatter in `SKILL.md`:

```yaml
---
name: bugs                    # Skill identifier (used for /bugs command)
description: Bug and ...      # Trigger description (Claude reads this to decide when to activate)
allowed-tools: Read, Grep, Glob, Bash, Write, Edit   # Tools the skill can use
---
```

**How triggering works:** Claude reads only the `description` field to decide if the skill is relevant to your request. Keywords like "bugs", "bug report", "signaler un bug" in the description tell Claude when to activate the skill.

---

## Python Client

A Python HTTP client is included for server-side integration (Flask, Django, FastAPI, etc.):

```python
from clients.python.bugs_client import BugsClient

client = BugsClient(
    base_url="http://localhost:9010",
    api_key="YOUR_PROJECT_API_KEY"
)

# List open bugs
issues, error = client.list_issues(status="nouveau,en_cours")

# Create a bug
issue, error = client.create_issue({
    "type": "bug",
    "title": "Payment fails on checkout",
    "priority": "critique",
    "reporter": "backend-service"
})

# Update status
result, error = client.update_status(
    "BUG-001",
    status="en_cours",
    assignee="Pierre",
    comment="Investigating"
)

# Upload a screenshot
with open("screenshot.png", "rb") as f:
    attachment, error = client.upload_attachment("BUG-001", f)

# Get stats
stats, error = client.get_stats()
```

All methods return `(data, None)` on success or `(None, error_string)` on failure.

### Flask Integration Example

```python
# config.py
BUGS_SERVICE_URL = "http://localhost:9010"
BUGS_SERVICE_API_KEY = "YOUR_PROJECT_API_KEY"

# routes.py
from bugs_client import BugsClient

@app.route("/api/report-bug", methods=["POST"])
def report_bug():
    client = BugsClient(
        app.config["BUGS_SERVICE_URL"],
        app.config["BUGS_SERVICE_API_KEY"]
    )
    data = request.json
    issue, error = client.create_issue({
        "type": "bug",
        "title": data["title"],
        "description": data.get("description", ""),
        "priority": data.get("priority", "normale"),
        "reporter": current_user.email,
        "context_data": {
            "url": data.get("url"),
            "user_agent": request.headers.get("User-Agent"),
        }
    })
    if error:
        return jsonify({"error": error}), 500
    return jsonify(issue), 201
```

---

## API Reference

### Authentication

All endpoints (except `/health`) require authentication:

| Method | Header | Access Level |
|--------|--------|--------------|
| Bearer token (API key) | `Authorization: Bearer {API_KEY}` | Project-scoped |
| Bearer token (master key) | `Authorization: Bearer {ADMIN_MASTER_KEY}` | Admin (all projects) |
| Basic auth | `Authorization: Basic {base64(user:pass)}` | User-scoped |

### Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | None | Health check |
| **Admin** | | | |
| `POST` | `/api/v1/admin/projects` | Admin | Create project (returns API key) |
| `GET` | `/api/v1/admin/projects` | Admin | List all projects |
| `PATCH` | `/api/v1/admin/projects/{id}` | Admin | Update project (rename, enable/disable) |
| `POST` | `/api/v1/admin/projects/{id}/regenerate-key` | Admin | Regenerate API key |
| `POST` | `/api/v1/admin/users` | Admin | Create user |
| `GET` | `/api/v1/admin/users` | Admin | List users |
| `DELETE` | `/api/v1/admin/users/{id}` | Admin | Delete user |
| **Issues** | | | |
| `POST` | `/api/v1/issues` | Project key | Create issue |
| `GET` | `/api/v1/issues` | Any | List issues (filters: status, type, priority, assignee) |
| `GET` | `/api/v1/issues/{reference}` | Any | Get issue + comments + attachments + history |
| `PUT` | `/api/v1/issues/{reference}` | Any | Update issue fields |
| `PATCH` | `/api/v1/issues/{reference}/status` | Any | Change status (+ optional assignee/comment) |
| `DELETE` | `/api/v1/issues/{reference}` | Any | Delete issue |
| **Comments** | | | |
| `POST` | `/api/v1/issues/{reference}/comments` | Any | Add comment |
| `GET` | `/api/v1/issues/{reference}/comments` | Any | List comments |
| **Attachments** | | | |
| `POST` | `/api/v1/issues/{reference}/attachments` | Any | Upload file (PNG, JPEG, GIF, WebP, MP4, WebM, PDF — max 10MB) |
| `GET` | `/api/v1/attachments/{id}` | None | Download file |
| `GET` | `/api/v1/attachments/{id}/thumbnail` | None | Get image thumbnail (300x300) |
| **Stats** | | | |
| `GET` | `/api/v1/stats` | Any | Counts by status/type/priority |

### Issue Types & Statuses

**Types:** `bug`, `suggestion`, `feature`, `improvement`

**Priorities:** `basse`, `normale`, `haute`, `critique`

**Status workflow:**
```
nouveau ──> en_cours ──> a_approuver ──> termine
                    └──> rejete
```

### Response Format

**List issues:**
```json
{
  "data": [
    {
      "id": 1,
      "reference": "BUG-001",
      "type": "bug",
      "title": "Login button broken",
      "status": "nouveau",
      "priority": "haute",
      "reporter": "Pierre",
      "created_at": "2026-01-15T10:30:00",
      "comments_count": 2,
      "attachments_count": 1
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 42, "pages": 3 }
}
```

**Issue detail:**
```json
{
  "issue": { ... },
  "comments": [
    { "id": 1, "author": "Pierre", "content": "Investigating...", "type": "comment", "created_at": "..." }
  ],
  "attachments": [
    { "id": 1, "filename": "screenshot.png", "mime_type": "image/png", "size_bytes": 45231 }
  ],
  "history": [
    { "field": "status", "old": "nouveau", "new": "en_cours", "by": "Pierre", "at": "..." }
  ]
}
```

### Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid data or duplicate slug |
| 401 | Invalid or missing API key |
| 403 | Admin access required |
| 404 | Issue/project/attachment not found |
| 422 | Validation error |

---

## Architecture

```
docker compose
├── bugs-backend (FastAPI, port 8000 internal)
│   ├── main.py              # API endpoints + auth + schemas
│   ├── models.py            # SQLAlchemy ORM models
│   ├── database.py          # SQLite connection
│   └── services/
│       └── attachment_service.py  # File upload + thumbnails
│
├── bugs-frontend (nginx, port 9010 external)
│   ├── nginx.conf           # Reverse proxy + security headers
│   └── static/              # SPA dashboard (pre-built)
│
└── Volumes
    ├── data/db/             # SQLite database (bugs.db)
    ├── data/uploads/        # File attachments
    └── data/backups/        # Manual backups
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `users` | Admin/operator accounts |
| `projects` | Projects with API keys (hashed) and webhook URLs |
| `issues` | Bugs/suggestions with full metadata |
| `comments` | Issue comments (including status change logs) |
| `attachments` | File metadata + storage paths |
| `issue_history` | Audit trail of every field change |

### Security

- API keys are hashed with SHA256 (plaintext never stored)
- Passwords hashed with SHA256 + random salt
- nginx security headers: X-Frame-Options, X-Content-Type-Options, CSP, etc.
- CORS enabled (configurable)
- Max upload size: 10MB (backend) / 15MB (nginx)

### Default Admin User

On first startup (empty database), a default admin is created:
- Username: `admin`
- Password: `admin123`

**Change this immediately** via the admin API or by setting environment variables.

---

## Health Check Monitoring Integration

The bugs service can receive **automatic bug reports from a health monitor**. When a service goes down, a bug is created. When it comes back up, the bug is auto-resolved. This creates a full incident log with exact downtime tracking.

### How It Works

```
Health Monitor                    Bugs Service                    Webhook Listener
(polls every 60s)                 (port 9010)                     (port 9876)

 1. GET /health ──> Service
    Response: timeout/error

 2. fail_count++
    (retry after 60s)

 3. 2nd failure = DOWN
    POST /api/v1/issues ────────> 4. Create issue BUG-042
    {                                 (priority: critique)
      type: "bug",
      title: "[MONITOR]              5. Trigger webhook ──────────> 6. Receive notification
        MyApp is DOWN",                  POST to webhook_url           - Sync bug to local files
      priority: "critique",                                            - Send Telegram alert
      reporter: "Health Monitor"                                       - Send Discord alert
    }

    ... service is down ...

 7. Service responds again!
    POST /comments ──────────────> 8. Add resolution comment
    {                                  "MyApp is back.
      author: "Health Monitor",         Downtime: 12m 34s"
      content: "Back online.
        Downtime: 12m 34s"        9. PATCH /status ──────────────> Auto-close BUG-042
    }                                  {status: "termine"}
```

### Setting Up a Health Monitor

#### 1. Create a project for your monitor

```bash
export ADMIN_KEY="your_admin_master_key"

curl -X POST "http://localhost:9010/api/v1/admin/projects" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Health Monitor",
    "slug": "health-monitor",
    "webhook_url": "http://your-webhook-listener:9876"
  }'
```

Save the returned `api_key`.

#### 2. Monitor script (Python example)

```python
"""
Minimal health monitor that creates/resolves bugs automatically.
Run as a cron job or long-running service.
"""
import time
import requests
from datetime import datetime

BUGS_API = "http://localhost:9010/api/v1"
API_KEY = "YOUR_HEALTH_MONITOR_API_KEY"
CHECK_INTERVAL = 60  # seconds
RETRIES_BEFORE_DOWN = 2

SERVICES = [
    {"name": "My Web App", "url": "http://localhost:3000/health", "port": 3000},
    {"name": "My API",     "url": "http://localhost:8080/health", "port": 8080},
    {"name": "Database",   "url": "http://localhost:5432/",       "port": 5432},
]

# Track state per service
states = {s["name"]: {"status": "up", "fail_count": 0, "bug_ref": None, "down_since": None}
          for s in SERVICES}


def check_health(url, timeout=10):
    """Returns True if service responds with 2xx."""
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 400
    except Exception:
        return False


def bugs_request(method, path, data=None):
    """Authenticated request to bugs service."""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    r = requests.request(method, f"{BUGS_API}{path}", json=data, headers=headers, timeout=10)
    return r.json() if r.ok else None


def create_down_bug(name, url, port):
    """Create a critical bug when service goes DOWN."""
    result = bugs_request("POST", "/issues", {
        "type": "bug",
        "title": f"[MONITOR] {name} is DOWN (port {port})",
        "description": (
            f"Health monitor detected that **{name}** is not responding.\n\n"
            f"- **URL:** {url}\n"
            f"- **Port:** {port}\n"
            f"- **Detected at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Consecutive failures:** {RETRIES_BEFORE_DOWN}"
        ),
        "priority": "critique",
        "reporter": "Health Monitor",
    })
    return result.get("reference") if result else None


def resolve_bug(reference, name, downtime):
    """Add resolution comment and close the bug."""
    bugs_request("POST", f"/issues/{reference}/comments", {
        "author": "Health Monitor",
        "content": f"**{name}** is back online. Downtime: {downtime}.",
    })
    bugs_request("PATCH", f"/issues/{reference}/status", {
        "status": "termine",
        "comment": f"Auto-resolved. Downtime: {downtime}",
    })


def format_duration(td):
    """Format timedelta as human-readable string."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


# Main loop
while True:
    for service in SERVICES:
        name = service["name"]
        state = states[name]
        alive = check_health(service["url"])

        if alive:
            if state["status"] == "down":
                # Service restored!
                downtime = format_duration(datetime.now() - state["down_since"])
                if state["bug_ref"]:
                    resolve_bug(state["bug_ref"], name, downtime)
                    print(f"[RESOLVED] {name} back online after {downtime} (bug {state['bug_ref']})")
                state["status"] = "up"
                state["bug_ref"] = None
                state["down_since"] = None
            state["fail_count"] = 0

        else:
            state["fail_count"] += 1
            if state["fail_count"] >= RETRIES_BEFORE_DOWN and state["status"] == "up":
                # Service is DOWN
                state["status"] = "down"
                state["down_since"] = datetime.now()
                ref = create_down_bug(name, service["url"], service["port"])
                state["bug_ref"] = ref
                print(f"[DOWN] {name} — created bug {ref}")

    time.sleep(CHECK_INTERVAL)
```

#### 3. Webhook listener (optional, for notifications)

If you configure a `webhook_url` on the project, the bugs service sends a POST on every new issue:

```json
{
  "event": "issue_created",
  "project": {"id": 1, "name": "Health Monitor", "slug": "health-monitor"},
  "issue": {
    "reference": "BUG-042",
    "type": "bug",
    "title": "[MONITOR] My API is DOWN (port 8080)",
    "priority": "critique",
    "status": "nouveau",
    "reporter": "Health Monitor",
    "created_at": "2026-03-08T14:30:00"
  }
}
```

Use this to trigger Slack/Discord/Telegram/PagerDuty notifications.

**Simple webhook receiver example:**

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = json.loads(body)

        issue = payload["issue"]
        project = payload["project"]
        print(f"New bug: {issue['reference']} — {issue['title']} ({project['name']})")

        # Send to Slack, Discord, Telegram, etc.
        # send_slack_notification(issue)
        # send_discord_embed(issue)

        self.send_response(200)
        self.end_headers()

HTTPServer(("0.0.0.0", 9876), WebhookHandler).serve_forever()
```

### Features

| Feature | Description |
|---------|-------------|
| **Auto-create bugs** | Service DOWN -> critical bug created automatically |
| **Auto-resolve bugs** | Service UP -> bug closed with downtime in comment |
| **Downtime tracking** | Exact duration recorded (e.g. "12m 34s") |
| **Flap protection** | Optional: suppress alerts if service bounces >5 times in 10 min |
| **Webhook notifications** | POST to any URL on issue creation |
| **Audit trail** | Full history: when it went down, who resolved it, how long |
| **Multi-service** | Monitor as many services as needed, all report to same tracker |

### What Gets Stored Per Incident

Each DOWN event creates a bug with:

```
Title:       [MONITOR] My API is DOWN (port 8080)
Type:        bug
Priority:    critique
Reporter:    Health Monitor
Status:      nouveau -> en_cours -> termine (auto-resolved)

Comments:
  - [Health Monitor] My API is back online. Downtime: 12m 34s.

History:
  - status: nouveau -> termine (by: Health Monitor)
```

This gives you a **complete incident log** searchable via the API or dashboard.

---

## Development

### Run without Docker

```bash
pip install -r requirements.txt
export ADMIN_MASTER_KEY=$(openssl rand -hex 32)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run tests

```bash
pip install -r requirements-dev.txt
pytest test_bugs.py -v
```

### Lint

```bash
pip install ruff
ruff check . --select=E,F,W --ignore=E501
```

---

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`) runs on push/PR to main:

1. **Lint** — ruff check
2. **Tests** — pytest
3. **Notify** — Discord webhook (optional, configure `DISCORD_WEBHOOK_URL` secret)

### Auto-deploy (optional)

A cron-based deploy script is included in `scripts/auto-deploy-tag.sh`. It watches for new git tags and rebuilds containers automatically.

---

## License

MIT
