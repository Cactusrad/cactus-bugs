# Composants Bug Report Button

## React Component

```tsx
// BugReportButton.tsx
import { useState } from 'react';

interface BugReportProps {
  apiKey: string;
  projectSlug: string;
  reporter?: string;
}

export function BugReportButton({ apiKey, projectSlug, reporter = 'anonymous' }: BugReportProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<'bug' | 'suggestion'>('bug');
  const [priority, setPriority] = useState<'basse' | 'normale' | 'haute' | 'critique'>('normale');
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const captureScreenshot = async () => {
    try {
      const canvas = await html2canvas(document.body);
      canvas.toBlob((blob) => {
        if (blob) {
          const file = new File([blob], 'screenshot.png', { type: 'image/png' });
          setScreenshot(file);
        }
      });
    } catch (e) {
      console.error('Screenshot failed:', e);
    }
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
    <!-- Floating button -->
    <button v-if="!isOpen" @click="isOpen = true" class="bug-btn">🐛</button>

    <!-- Modal -->
    <div v-if="isOpen" class="bug-modal">
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
          <span v-if="screenshot" class="ready">✓ Pret</span>
        </div>

        <button @click="submit" :disabled="loading || !title.trim()" class="submit">
          {{ loading ? 'Envoi...' : 'Envoyer le rapport' }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
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

const captureScreenshot = async () => {
  const canvas = await html2canvas(document.body);
  canvas.toBlob((blob) => {
    if (blob) screenshot.value = new File([blob], 'screenshot.png', { type: 'image/png' });
  });
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
</style>
```

---

## HTML Vanilla

```html
<!-- bug-report.html - Ajouter avant </body> -->
<div id="bug-report-widget"></div>

<script>
(function() {
  const CONFIG = {
    apiKey: 'PRO_xxx...', // Remplacer par votre API key
    reporter: 'anonymous'
  };

  const API_URL = 'http://localhost:9010/api/v1';

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
      <button class="submit" onclick="submitBugReport()">Envoyer le rapport</button>
    </div>
  `;

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
      alert('Bug signale avec succes!');
      closeBugModal();
      document.getElementById('bug-title').value = '';
      document.getElementById('bug-desc').value = '';
    }
  };
})();
</script>
```
