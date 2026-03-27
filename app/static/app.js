const fileInput = document.getElementById('fileInput');
const output = document.getElementById('output');
const statusEl = document.getElementById('status');
const form = document.getElementById('uploadForm');
const parseBtn = document.getElementById('parseBtn');

function setStatus(msg, ok=false){statusEl.textContent = msg; statusEl.className = 'status ' + (ok ? 'ok':'err');}

parseBtn.addEventListener('click', async ()=>{
  const file = fileInput.files[0];
  if(!file){ setStatus('יש לבחור קובץ PDF קודם.'); return; }
  const fd = new FormData(); fd.append('file', file);
  setStatus('מחלץ נתונים...');
  try{
    const res = await fetch('/parse', {method:'POST', body: fd});
    if(!res.ok) throw new Error('Parse failed');
    const data = await res.json();
    output.textContent = JSON.stringify(data, null, 2);
    setStatus('החילוץ בוצע.', true);
  }catch(err){
    setStatus('שגיאה בחילוץ הנתונים.');
  }
});

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const file = fileInput.files[0];
  if(!file){ setStatus('יש לבחור קובץ PDF קודם.'); return; }
  const fd = new FormData(); fd.append('file', file);
  setStatus('מייצר טופס ממולא...');
  try{
    const res = await fetch('/generate', {method:'POST', body: fd});
    if(!res.ok) throw new Error('Generate failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'fenix_filled.pdf'; a.click();
    URL.revokeObjectURL(url);
    setStatus('הקובץ ירד בהצלחה.', true);
  }catch(err){
    setStatus('שגיאה ביצירת הטופס.');
  }
});
