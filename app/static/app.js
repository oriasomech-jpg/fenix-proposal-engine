const fileInput = document.getElementById('fileInput');
const output = document.getElementById('output');
const statusEl = document.getElementById('status');
const form = document.getElementById('uploadForm');
const parseBtn = document.getElementById('parseBtn');
const generateBtn = document.getElementById('generateBtn');

function setStatus(msg, ok = false) {
  statusEl.textContent = msg;
  statusEl.className = 'status ' + (ok ? 'ok' : 'err');
}

function getSelectedFile() {
  const file = fileInput?.files?.[0];
  if (!file) {
    setStatus('יש לבחור קובץ PDF קודם.');
    return null;
  }
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    setStatus('יש להעלות קובץ PDF בלבד.');
    return null;
  }
  return file;
}

async function callApi(url, file) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const res = await fetch(`${window.location.origin}${url}`, {
    method: 'POST',
    body: fd,
    cache: 'no-store',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  });
  return res;
}

parseBtn?.addEventListener('click', async () => {
  const file = getSelectedFile();
  if (!file) return;
  setStatus('מחלץ נתונים...');
  output.textContent = 'טוען...';
  try {
    const res = await callApi('/parse', file);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || `Parse failed (${res.status})`);
    }
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
    setStatus('החילוץ בוצע.', true);
  } catch (err) {
    console.error('parse error', err);
    output.textContent = err?.message || 'שגיאה בחילוץ';
    setStatus('שגיאה בחילוץ הנתונים.');
  }
});

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  e.stopPropagation();

  const file = getSelectedFile();
  if (!file) return;

  generateBtn.disabled = true;
  setStatus('מייצר טופס ממולא...');
  try {
    const res = await callApi('/generate', file);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || `Generate failed (${res.status})`);
    }

    const blob = await res.blob();
    if (!blob || blob.size === 0) {
      throw new Error('השרת החזיר קובץ ריק.');
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fenix_filled.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    setStatus('הקובץ ירד בהצלחה.', true);
  } catch (err) {
    console.error('generate error', err);
    setStatus('שגיאה ביצירת הטופס.');
    output.textContent = err?.message || 'שגיאה ביצירת הטופס';
  } finally {
    generateBtn.disabled = false;
  }
});
