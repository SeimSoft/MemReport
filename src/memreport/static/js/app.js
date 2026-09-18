/**
 * MemReport - Frontend Application Logic
 */

let currentDate = new Date();
let selectedDateStr = formatDate(currentDate);
let reportsMap = {}; // date -> summary object
let currentReport = null; // full report object for selectedDateStr
let isEditMode = false;
let isRawMode = false;
let mapInstance = null;
let mapClusterGroup = null;
let mapRoutesGroup = null;

// --- Helper Functions ---

function padZero(num) {
  return num < 10 ? '0' + num : num;
}

function formatDate(d) {
  return `${d.getFullYear()}-${padZero(d.getMonth() + 1)}-${padZero(d.getDate())}`;
}

function formatDateGerman(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  return dateObj.toLocaleDateString('de-DE', options);
}

// --- Initialization ---

window.addEventListener('DOMContentLoaded', async () => {
  initTheme();

  // Check URL query param ?date=YYYY-MM-DD
  const urlParams = new URLSearchParams(window.location.search);
  const dateQuery = urlParams.get('date');
  if (dateQuery && /^\d{4}-\d{2}-\d{2}$/.test(dateQuery)) {
    selectedDateStr = dateQuery;
    const [y, m, d] = dateQuery.split('-').map(Number);
    currentDate = new Date(y, m - 1, d || 1);
  }

  await loadReportsList();
  renderCalendar();
  await loadReportForDate(selectedDateStr);
});

window.addEventListener('popstate', (e) => {
  const urlParams = new URLSearchParams(window.location.search);
  const dateQuery = urlParams.get('date');
  if (dateQuery && /^\d{4}-\d{2}-\d{2}$/.test(dateQuery) && dateQuery !== selectedDateStr) {
    selectDate(dateQuery);
  }
});

// Keyboard shortcut to toggle sidebar: '['
window.addEventListener('keydown', (e) => {
  if ((e.key === '[' || e.key === ']') && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
    toggleSidebar();
  }
});

// --- Reports API & List ---

async function loadReportsList() {
  try {
    const res = await fetch('/api/reports');
    if (res.status === 401) {
      window.location.href = '/login';
      return;
    }
    if (!res.ok) throw new Error('Fehler beim Abrufen der Berichte');
    const list = await res.json();

    reportsMap = {};
    list.forEach(item => {
      reportsMap[item.date] = item;
    });

    document.getElementById('reports-count').textContent = list.length;
    renderSidebarReportsList(list);
    updateHeaderNavButtons();
  } catch (err) {
    console.error('Error loading reports:', err);
  }
}

function renderSidebarReportsList(list) {
  const container = document.getElementById('reports-list');
  container.innerHTML = '';

  if (!list || list.length === 0) {
    container.innerHTML = '<div class="text-xs text-muted p-2">Keine Berichte vorhanden</div>';
    return;
  }

  list.forEach(item => {
    const div = document.createElement('div');
    div.className = `report-item ${item.date === selectedDateStr ? 'active' : ''} ${item.is_liked ? 'is-liked' : ''}`;
    div.id = `report-item-${item.date}`;
    div.onclick = () => selectDate(item.date);

    const hasLikedIcon = item.is_liked
      ? `<span title="Favorit" class="text-rose-400">❤️</span>`
      : '';
    const hasGpsIcon = item.has_location
      ? `<span title="GPS hinterlegt" class="text-amber-400">📍</span>`
      : '';

    div.innerHTML = `
      <div class="report-item-date">
        <span>${item.date}</span>
        <div class="flex items-center gap-1">
          ${hasLikedIcon}
          ${hasGpsIcon}
        </div>
      </div>
      <div class="report-item-meta">
        <span>${item.content_type.toUpperCase()}</span>
        <span>•</span>
        <span>${(item.size_bytes / 1024).toFixed(1)} KB</span>
      </div>
    `;
    container.appendChild(div);
  });
}

function filterReportList() {
  const query = document.getElementById('report-search-input').value.toLowerCase();
  const filtered = Object.values(reportsMap).filter(item => item.date.includes(query));
  renderSidebarReportsList(filtered);
}

// --- Calendar Logic ---

function populateYearSelect(currentYear) {
  const select = document.getElementById('calendar-year-select');
  if (!select) return;

  const startYear = Math.min(currentYear - 8, 2015);
  const endYear = Math.max(currentYear + 8, 2035);

  select.innerHTML = '';
  for (let y = startYear; y <= endYear; y++) {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = y;
    if (y === currentYear) opt.selected = true;
    select.appendChild(opt);
  }
}

function renderCalendar() {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
  ];

  const monthEl = document.getElementById('calendar-month-name');
  if (monthEl) {
    monthEl.textContent = monthNames[month];
  }
  populateYearSelect(year);

  const firstDayIndex = (new Date(year, month, 1).getDay() + 6) % 7; // Monday = 0
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const grid = document.getElementById('calendar-grid');
  grid.innerHTML = '';

  // Empty leading days
  for (let i = 0; i < firstDayIndex; i++) {
    const emptyCell = document.createElement('div');
    emptyCell.className = 'calendar-day day-empty';
    grid.appendChild(emptyCell);
  }

  const todayStr = formatDate(new Date());

  // Actual days
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${padZero(month + 1)}-${padZero(d)}`;
    const cell = document.createElement('div');
    cell.className = 'calendar-day';
    cell.textContent = d;

    if (dateStr === todayStr) cell.classList.add('day-today');
    if (dateStr === selectedDateStr) cell.classList.add('day-selected');

    // Check if report exists
    const reportItem = reportsMap[dateStr];
    const hasReport = !!reportItem;
    const hasGps = hasReport && reportItem.has_location;
    const isLiked = hasReport && reportItem.is_liked;

    if (isLiked) {
      cell.classList.add('is-liked');
      cell.title = 'Favorit';
    }

    if (hasReport || hasGps || isLiked) {
      const ind = document.createElement('div');
      ind.className = 'day-indicators';
      if (hasReport) {
        const dot = document.createElement('span');
        dot.className = 'indicator-dot dot-report';
        ind.appendChild(dot);
      }
      if (isLiked) {
        const dot = document.createElement('span');
        dot.className = 'indicator-dot dot-like';
        ind.appendChild(dot);
      }
      if (hasGps) {
        const dot = document.createElement('span');
        dot.className = 'indicator-dot dot-gps';
        ind.appendChild(dot);
      }
      cell.appendChild(ind);
    }

    cell.onclick = () => selectDate(dateStr);
    grid.appendChild(cell);
  }
}

function changeMonth(delta) {
  currentDate.setMonth(currentDate.getMonth() + delta);
  renderCalendar();
}

function changeYear(delta) {
  currentDate.setFullYear(currentDate.getFullYear() + delta);
  renderCalendar();
}

function onYearSelectChange(newYear) {
  currentDate.setFullYear(parseInt(newYear, 10));
  renderCalendar();
}

function jumpToToday() {
  currentDate = new Date();
  switchMainView('report');
  selectDate(formatDate(currentDate));
}

// --- Sidebar Controls (Desktop Collapse & Mobile Drawer) ---

function toggleSidebar() {
  if (window.innerWidth <= 900) {
    toggleMobileSidebar();
  } else {
    const layout = document.getElementById('app-layout');
    if (layout) {
      layout.classList.toggle('sidebar-collapsed');
    }
  }
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById('app-sidebar');
  const overlay = document.getElementById('mobile-sidebar-overlay');
  const isOpen = sidebar.classList.toggle('mobile-open');
  if (isOpen) {
    overlay.classList.remove('hidden');
  } else {
    overlay.classList.add('hidden');
  }
}

function closeMobileSidebar() {
  const sidebar = document.getElementById('app-sidebar');
  const overlay = document.getElementById('mobile-sidebar-overlay');
  if (sidebar) sidebar.classList.remove('mobile-open');
  if (overlay) overlay.classList.add('hidden');
}

async function selectDate(dateStr) {
  selectedDateStr = dateStr;
  const [y, m, d] = dateStr.split('-').map(Number);
  currentDate = new Date(y, m - 1, d);

  renderCalendar();
  closeMobileSidebar();

  // Update URL query parameter without full page reload
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('date', dateStr);
    window.history.replaceState({ date: dateStr }, '', url.toString());
  } catch (e) {}

  // Update active item in sidebar
  document.querySelectorAll('.report-item').forEach(el => el.classList.remove('active'));
  const activeItem = document.getElementById(`report-item-${dateStr}`);
  if (activeItem) {
    activeItem.classList.add('active');
    try {
      activeItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } catch (e) {}
  }

  if (isEditMode) cancelEditMode();
  updateHeaderNavButtons();
  await loadReportForDate(dateStr);
}

// --- Chronological Report Navigation (< >) ---

function getSortedReportDates() {
  return Object.keys(reportsMap).sort();
}

function updateHeaderNavButtons() {
  const prevBtn = document.getElementById('btn-report-prev');
  const nextBtn = document.getElementById('btn-report-next');
  if (!prevBtn || !nextBtn) return;

  const dates = getSortedReportDates();
  if (!dates.length) {
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    prevBtn.title = 'Keine Berichte vorhanden';
    nextBtn.title = 'Keine Berichte vorhanden';
    return;
  }

  const currentDateStr = selectedDateStr || formatDate(currentDate);
  const olderDates = dates.filter(d => d < currentDateStr);
  const newerDates = dates.filter(d => d > currentDateStr);

  if (olderDates.length > 0) {
    prevBtn.disabled = false;
    const target = olderDates[olderDates.length - 1];
    prevBtn.title = `Vorheriger Bericht (${formatDateGerman(target)})`;
  } else {
    prevBtn.disabled = true;
    prevBtn.title = 'Kein früherer Bericht vorhanden';
  }

  if (newerDates.length > 0) {
    nextBtn.disabled = false;
    const target = newerDates[0];
    nextBtn.title = `Nächster Bericht (${formatDateGerman(target)})`;
  } else {
    nextBtn.disabled = true;
    nextBtn.title = 'Kein späterer Bericht vorhanden';
  }
}

function navigateReport(direction) {
  const dates = getSortedReportDates();
  if (!dates.length) return;

  const currentDateStr = selectedDateStr || formatDate(currentDate);
  if (direction < 0) {
    const olderDates = dates.filter(d => d < currentDateStr);
    if (olderDates.length > 0) {
      const targetDate = olderDates[olderDates.length - 1];
      selectDate(targetDate);
    }
  } else if (direction > 0) {
    const newerDates = dates.filter(d => d > currentDateStr);
    if (newerDates.length > 0) {
      const targetDate = newerDates[0];
      selectDate(targetDate);
    }
  }
}

// --- Report Loading & Rendering ---

async function loadReportForDate(dateStr) {
  resetAudioPlayer();
  document.getElementById('current-date-heading').textContent = formatDateGerman(dateStr);
  isRawMode = false;
  document.getElementById('raw-toggle-text').textContent = 'Quelltext';

  try {
    const res = await fetch(`/api/reports/${dateStr}`);

    if (res.status === 404) {
      // Empty state
      currentReport = null;
      showEmptyState();
      updateLocationBadge(null);
      return;
    }

    if (!res.ok) throw new Error('Fehler beim Laden des Berichts');

    currentReport = await res.json();
    showReportContent(currentReport);
    updateLocationBadge(currentReport);
  } catch (err) {
    console.error('Error loading report for date:', err);
  }
}

function showEmptyState() {
  document.getElementById('report-rendered-view').classList.add('hidden');
  document.getElementById('report-raw-view').classList.add('hidden');
  document.getElementById('report-editor-view').classList.add('hidden');
  document.getElementById('report-empty-state').classList.remove('hidden');

  document.getElementById('btn-toggle-raw').disabled = true;

  const ttsBtn = document.getElementById('btn-read-aloud');
  if (ttsBtn) ttsBtn.disabled = true;

  const actionDateEl = document.getElementById('sidebar-action-date');
  if (actionDateEl) actionDateEl.textContent = selectedDateStr;

  const likeBtn = document.getElementById('btn-report-like');
  const likeText = document.getElementById('report-like-text');
  const headerLikeBadge = document.getElementById('header-like-badge');
  if (likeBtn) {
    likeBtn.disabled = true;
    likeBtn.classList.remove('liked');
    if (likeText) likeText.textContent = 'Favorit';
  }
  if (headerLikeBadge) headerLikeBadge.classList.add('hidden');

  ['btn-edit-report', 'btn-share-date', 'btn-export-report', 'btn-delete-report'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = true;
  });
}

function showReportContent(report) {
  document.getElementById('report-empty-state').classList.add('hidden');
  document.getElementById('report-editor-view').classList.add('hidden');
  document.getElementById('report-rendered-view').classList.remove('hidden');
  document.getElementById('report-raw-view').classList.add('hidden');
  document.getElementById('btn-toggle-raw').disabled = false;

  const ttsBtn = document.getElementById('btn-read-aloud');
  if (ttsBtn) ttsBtn.disabled = false;

  const actionDateEl = document.getElementById('sidebar-action-date');
  if (actionDateEl) actionDateEl.textContent = report.date;

  const likeBtn = document.getElementById('btn-report-like');
  const likeText = document.getElementById('report-like-text');
  const headerLikeBadge = document.getElementById('header-like-badge');
  if (likeBtn) {
    likeBtn.disabled = false;
    if (report.is_liked) {
      likeBtn.classList.add('liked');
      if (likeText) likeText.textContent = 'Gemerkt';
      if (headerLikeBadge) headerLikeBadge.classList.remove('hidden');
    } else {
      likeBtn.classList.remove('liked');
      if (likeText) likeText.textContent = 'Favorit';
      if (headerLikeBadge) headerLikeBadge.classList.add('hidden');
    }
  }

  ['btn-edit-report', 'btn-share-date', 'btn-export-report', 'btn-delete-report'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = false;
  });

  renderMarkdownAndHtml(report.content, document.getElementById('rendered-content'));
  document.getElementById('raw-content-code').textContent = report.content;
}

async function toggleCurrentReportLike() {
  if (!currentReport || !currentReport.date) return;

  const likeBtn = document.getElementById('btn-report-like');
  const likeText = document.getElementById('report-like-text');
  const headerLikeBadge = document.getElementById('header-like-badge');

  try {
    const res = await fetch(`/api/reports/${currentReport.date}/like`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    if (!res.ok) throw new Error('Fehler beim Aktualisieren des Favoriten-Status');
    const data = await res.json();

    currentReport.is_liked = data.is_liked;
    if (reportsMap[currentReport.date]) {
      reportsMap[currentReport.date].is_liked = data.is_liked;
    }

    if (data.is_liked) {
      if (likeBtn) likeBtn.classList.add('liked');
      if (likeText) likeText.textContent = 'Gemerkt';
      if (headerLikeBadge) headerLikeBadge.classList.remove('hidden');
    } else {
      if (likeBtn) likeBtn.classList.remove('liked');
      if (likeText) likeText.textContent = 'Favorit';
      if (headerLikeBadge) headerLikeBadge.classList.add('hidden');
    }

    // Immediately re-render calendar and reports list
    renderCalendar();
    renderSidebarReportsList(Object.values(reportsMap));
  } catch (err) {
    console.error('Error toggling report like:', err);
  }
}

function renderMarkdownAndHtml(rawContent, container) {
  if (!rawContent) {
    container.innerHTML = '<p class="text-muted">Kein Inhalt vorhanden.</p>';
    return;
  }

  // Parse markdown with marked (preserves inline HTML)
  marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: true,
  });

  const parsedHtml = marked.parse(rawContent);
  container.innerHTML = parsedHtml;

  // Render interactive widgets (Leaflet maps, Plotly charts) FIRST before hljs
  renderInteractiveComponents(container);

  // Highlight.js for remaining code blocks
  container.querySelectorAll('pre code').forEach((block) => {
    hljs.highlightElement(block);
  });

  // KaTeX auto-render for LaTeX formulas
  if (window.renderMathInElement) {
    renderMathInElement(container, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\(', right: '\\)', display: false },
        { left: '\\[', right: '\\]', display: true }
      ],
      throwOnError: false
    });
  }
}

function toggleRawSource() {
  if (!currentReport) return;
  isRawMode = !isRawMode;
  const renderedView = document.getElementById('report-rendered-view');
  const rawView = document.getElementById('report-raw-view');
  const toggleBtnText = document.getElementById('raw-toggle-text');

  if (isRawMode) {
    renderedView.classList.add('hidden');
    rawView.classList.remove('hidden');
    toggleBtnText.textContent = 'Vorschau';
  } else {
    renderedView.classList.remove('hidden');
    rawView.classList.add('hidden');
    toggleBtnText.textContent = 'Quelltext';
  }
}

// --- In-Viewer Editor ---

function enterEditMode() {
  isEditMode = true;
  document.getElementById('report-rendered-view').classList.add('hidden');
  document.getElementById('report-raw-view').classList.add('hidden');
  document.getElementById('report-empty-state').classList.add('hidden');
  document.getElementById('report-editor-view').classList.remove('hidden');

  document.getElementById('view-mode-buttons').classList.add('hidden');
  document.getElementById('edit-mode-buttons').classList.remove('hidden');

  const textarea = document.getElementById('report-editor-textarea');
  textarea.value = currentReport ? currentReport.content : '';
  textarea.focus();
}

function cancelEditMode() {
  isEditMode = false;
  document.getElementById('report-editor-view').classList.add('hidden');
  document.getElementById('view-mode-buttons').classList.remove('hidden');
  document.getElementById('edit-mode-buttons').classList.add('hidden');

  if (currentReport) {
    showReportContent(currentReport);
  } else {
    showEmptyState();
  }
}

async function saveReportEdit() {
  const text = document.getElementById('report-editor-textarea').value;
  try {
    const res = await fetch(`/api/reports/${selectedDateStr}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text })
    });

    if (!res.ok) throw new Error('Fehler beim Speichern des Berichts');

    currentReport = await res.json();
    await loadReportsList();
    renderCalendar();
    cancelEditMode();
  } catch (err) {
    alert(err.message);
  }
}

function createNewReportForDate() {
  enterEditMode();
  const textarea = document.getElementById('report-editor-textarea');
  textarea.value = `# Bericht für ${selectedDateStr}\n\n`;
}

function insertSnippet(before, after = '') {
  const textarea = document.getElementById('report-editor-textarea');
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selectedText = textarea.value.substring(start, end);
  const replacement = before + selectedText + after;
  textarea.value = textarea.value.substring(0, start) + replacement + textarea.value.substring(end);
  textarea.focus();
  textarea.setSelectionRange(start + before.length, start + before.length + selectedText.length);
}

async function deleteCurrentReport() {
  if (!confirm(`Möchtest du den Bericht für den ${selectedDateStr} wirklich löschen?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/reports/${selectedDateStr}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Löschen fehlgeschlagen');

    await loadReportsList();
    renderCalendar();
    await loadReportForDate(selectedDateStr);
  } catch (err) {
    alert(err.message);
  }
}

function downloadReport() {
  if (!currentReport) return;
  const blob = new Blob([currentReport.content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `report-${selectedDateStr}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// --- GPS Location Logic ---

function updateLocationBadge(report) {
  const badge = document.getElementById('location-badge-container');
  const text = document.getElementById('location-badge-text');
  if (!badge || !text) return;

  if (report && report.latitude && report.longitude) {
    badge.classList.add('has-location');
    const label = report.location_name || 'Standort hinterlegt';
    text.textContent = label;
    badge.title = `Standort: ${report.location_name || ''} (GPS: ${report.latitude.toFixed(4)}, ${report.longitude.toFixed(4)}) - Klicken zum Bearbeiten`;
  } else {
    badge.classList.remove('has-location');
    text.textContent = 'Ort hinzufügen';
    badge.title = 'GPS-Standort hinzufügen';
  }
}

// --- TTS Read Aloud (Google TTS) ---

function resetAudioPlayer() {
  const audio = document.getElementById('report-audio-element');
  const btn = document.getElementById('btn-read-aloud');
  const speakerIcon = btn ? btn.querySelector('.tts-speaker-icon') : null;
  const spinnerIcon = btn ? btn.querySelector('.tts-spinner-icon') : null;
  const label = document.getElementById('read-aloud-label');

  if (audio) {
    audio.pause();
    audio.removeAttribute('src');
  }
  if (btn) {
    btn.classList.remove('is-playing', 'is-loading');
  }
  if (speakerIcon) speakerIcon.classList.remove('hidden');
  if (spinnerIcon) spinnerIcon.classList.add('hidden');
  if (label) label.textContent = 'Vorlesen';
}

async function toggleReadAloud() {
  if (!selectedDateStr || !currentReport || !currentReport.content) {
    alert('Kein Bericht zum Vorlesen vorhanden.');
    return;
  }

  const audio = document.getElementById('report-audio-element');
  const btn = document.getElementById('btn-read-aloud');
  const speakerIcon = btn ? btn.querySelector('.tts-speaker-icon') : null;
  const spinnerIcon = btn ? btn.querySelector('.tts-spinner-icon') : null;
  const label = document.getElementById('read-aloud-label');

  if (!audio || !btn) return;

  // Toggle pause if currently playing
  if (!audio.paused && !audio.ended && audio.currentTime > 0) {
    audio.pause();
    btn.classList.remove('is-playing');
    if (label) label.textContent = 'Vorlesen';
    return;
  }

  // Resume if paused and same source
  const targetSrc = `/api/reports/${selectedDateStr}/audio`;
  if (audio.src && audio.src.endsWith(targetSrc) && audio.currentTime > 0 && !audio.ended) {
    audio.play();
    btn.classList.add('is-playing');
    if (label) label.textContent = 'Pause';
    return;
  }

  // Load new audio
  btn.classList.add('is-loading');
  if (spinnerIcon) spinnerIcon.classList.remove('hidden');
  if (speakerIcon) speakerIcon.classList.add('hidden');
  if (label) label.textContent = 'Erstelle Audio...';

  audio.src = targetSrc;
  audio.load();

  audio.oncanplaythrough = () => {
    btn.classList.remove('is-loading');
    btn.classList.add('is-playing');
    if (spinnerIcon) spinnerIcon.classList.add('hidden');
    if (speakerIcon) speakerIcon.classList.remove('hidden');
    if (label) label.textContent = 'Pause';
    audio.play();
  };

  audio.onended = () => {
    btn.classList.remove('is-playing', 'is-loading');
    if (spinnerIcon) spinnerIcon.classList.add('hidden');
    if (speakerIcon) speakerIcon.classList.remove('hidden');
    if (label) label.textContent = 'Vorlesen';
    audio.currentTime = 0;
  };

  audio.onerror = () => {
    btn.classList.remove('is-playing', 'is-loading');
    if (spinnerIcon) spinnerIcon.classList.add('hidden');
    if (speakerIcon) speakerIcon.classList.remove('hidden');
    if (label) label.textContent = 'Vorlesen';
    alert('Audio konnte nicht geladen oder generiert werden.');
  };
}

function openLocationModal() {
  document.getElementById('location-modal-date').textContent = selectedDateStr;
  const latInput = document.getElementById('loc-lat');
  const lonInput = document.getElementById('loc-lon');
  const nameInput = document.getElementById('loc-name');
  const deleteBtn = document.getElementById('btn-remove-location');

  if (currentReport && currentReport.latitude && currentReport.longitude) {
    latInput.value = currentReport.latitude;
    lonInput.value = currentReport.longitude;
    nameInput.value = currentReport.location_name || '';
    deleteBtn.classList.remove('hidden');
  } else {
    latInput.value = '';
    lonInput.value = '';
    nameInput.value = '';
    deleteBtn.classList.add('hidden');
  }

  document.getElementById('modal-location').classList.remove('hidden');
}

function closeLocationModal() {
  document.getElementById('modal-location').classList.add('hidden');
}

function useCurrentGeolocation() {
  if (!navigator.geolocation) {
    alert('Geolocation wird von diesem Browser nicht unterstützt.');
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      document.getElementById('loc-lat').value = pos.coords.latitude.toFixed(6);
      document.getElementById('loc-lon').value = pos.coords.longitude.toFixed(6);
    },
    (err) => {
      alert('Standort konnte nicht ermittelt werden: ' + err.message);
    }
  );
}

async function saveReportLocation() {
  const lat = parseFloat(document.getElementById('loc-lat').value);
  const lon = parseFloat(document.getElementById('loc-lon').value);
  const name = document.getElementById('loc-name').value.trim() || null;

  if (isNaN(lat) || isNaN(lon)) {
    alert('Bitte gültige Koordinaten eingeben');
    return;
  }

  try {
    const res = await fetch(`/api/reports/${selectedDateStr}/location`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latitude: lat, longitude: lon, name })
    });

    if (!res.ok) throw new Error('Standort speichern fehlgeschlagen');

    currentReport = await res.json();
    await loadReportsList();
    renderCalendar();
    updateLocationBadge(currentReport);
    closeLocationModal();
  } catch (err) {
    alert(err.message);
  }
}

async function deleteReportLocation() {
  try {
    const res = await fetch(`/api/reports/${selectedDateStr}/location`, {
      method: 'DELETE'
    });

    if (!res.ok) throw new Error('Standort löschen fehlgeschlagen');

    currentReport = await res.json();
    await loadReportsList();
    renderCalendar();
    updateLocationBadge(currentReport);
    closeLocationModal();
  } catch (err) {
    alert(err.message);
  }
}

// --- Map View Logic ---

function switchMainView(view) {
  const reportTab = document.getElementById('view-btn-report');
  const mapTab = document.getElementById('view-btn-map');
  const reportPane = document.getElementById('pane-report');
  const mapPane = document.getElementById('pane-map');

  if (view === 'report') {
    reportTab.classList.add('active');
    mapTab.classList.remove('active');
    reportPane.classList.add('active');
    mapPane.classList.remove('active');
  } else {
    mapTab.classList.add('active');
    reportTab.classList.remove('active');
    mapPane.classList.add('active');
    reportPane.classList.remove('active');
    initMainMap();
  }
}

async function initMainMap() {
  if (!mapInstance) {
    mapInstance = L.map('leaflet-map-container', {
      zoomControl: true,
      scrollWheelZoom: true
    }).setView([51.1657, 10.4515], 6);

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(mapInstance);

    // Layer group for GPS activity routes
    mapRoutesGroup = L.layerGroup().addTo(mapInstance);

    // MarkerCluster group for aggregated count bubbles
    if (window.L && L.markerClusterGroup) {
      mapClusterGroup = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 45,
        spiderfyOnMaxZoom: true,
        iconCreateFunction: function(cluster) {
          const count = cluster.getChildCount();
          let sizeClass = '';
          let iconSize = [36, 36];
          if (count >= 10) {
            sizeClass = 'cluster-large';
            iconSize = [48, 48];
          } else if (count >= 4) {
            sizeClass = 'cluster-medium';
            iconSize = [42, 42];
          }
          return L.divIcon({
            html: `<div class="count-bubble ${sizeClass}">${count}</div>`,
            className: 'count-cluster-icon',
            iconSize: iconSize,
            iconAnchor: [iconSize[0] / 2, iconSize[1] / 2]
          });
        }
      });

      // When clicking a cluster at max zoom, show popup listing reports
      mapClusterGroup.on('clusterclick', function(c) {
        if (mapInstance.getZoom() >= 14 && c.layer && c.layer.getAllChildMarkers) {
          const markers = c.layer.getAllChildMarkers();
          if (markers.length > 1) {
            let html = `<div class="cluster-popup-container">
              <div class="cluster-popup-title"><span>${markers.length} Berichte hier</span></div>`;
            markers.forEach(m => {
              if (m._reportData) {
                const rep = m._reportData;
                html += `
                  <div class="cluster-item">
                    <div class="cluster-item-header">
                      <span class="cluster-item-date">${rep.date}</span>
                      <span class="cluster-item-loc">${rep.location_name || 'Standort'}</span>
                    </div>
                    <button class="btn btn-primary btn-xs cluster-item-btn" onclick="jumpFromMapToReport('${rep.date}')">
                      Bericht öffnen
                    </button>
                  </div>
                `;
              }
            });
            html += `</div>`;
            L.popup().setLatLng(c.latlng).setContent(html).openOn(mapInstance);
          }
        }
      });

      mapInstance.addLayer(mapClusterGroup);
    } else {
      mapClusterGroup = L.layerGroup().addTo(mapInstance);
    }

    // Zoom listener for efficient route rendering
    mapInstance.on('zoomend', updateMapRoutesVisibility);

    // Click on map to set coordinates for current date
    mapInstance.on('click', (e) => {
      const { lat, lng } = e.latlng;
      if (confirm(`Möchtest du die Koordinaten ${lat.toFixed(4)}, ${lng.toFixed(4)} dem Bericht ${selectedDateStr} zuweisen?`)) {
        document.getElementById('loc-lat').value = lat.toFixed(6);
        document.getElementById('loc-lon').value = lng.toFixed(6);
        saveReportLocation();
      }
    });
  }

  setTimeout(() => {
    mapInstance.invalidateSize();
    loadMapLocations();
  }, 200);
}

function updateMapRoutesVisibility() {
  if (!mapInstance || !mapRoutesGroup) return;
  // Anti-lag: Only display detailed GPS route tracks from zoom level 9 and closer
  const zoom = mapInstance.getZoom();
  if (zoom >= 9) {
    if (!mapInstance.hasLayer(mapRoutesGroup)) {
      mapInstance.addLayer(mapRoutesGroup);
    }
  } else {
    if (mapInstance.hasLayer(mapRoutesGroup)) {
      mapInstance.removeLayer(mapRoutesGroup);
    }
  }
}

async function loadMapLocations() {
  if (!mapClusterGroup || !mapRoutesGroup) return;
  mapClusterGroup.clearLayers();
  mapRoutesGroup.clearLayers();

  try {
    const res = await fetch('/api/locations');
    if (!res.ok) throw new Error('Fehler beim Laden der Standorte');
    const locations = await res.json();

    const bounds = [];

    locations.forEach(loc => {
      bounds.push([loc.latitude, loc.longitude]);

      // 1. Cluster pin with count 1
      const singleIcon = L.divIcon({
        html: `<div class="count-bubble cluster-single" title="${loc.location_name || loc.date}">1</div>`,
        className: 'count-cluster-icon',
        iconSize: [36, 36],
        iconAnchor: [18, 18]
      });

      const marker = L.marker([loc.latitude, loc.longitude], { icon: singleIcon });
      marker._reportData = loc;

      marker.bindPopup(`
        <div class="map-popup-card">
          <div class="text-xs font-bold text-primary mb-1">${loc.date}</div>
          <h4 class="font-bold text-sm mb-1">${loc.location_name || 'Standort'}</h4>
          ${loc.snippet ? `<p class="text-xs text-muted mb-2 italic">"${loc.snippet}..."</p>` : ''}
          <button class="btn btn-primary btn-xs w-full" onclick="jumpFromMapToReport('${loc.date}')">
            Bericht öffnen
          </button>
        </div>
      `);
      mapClusterGroup.addLayer(marker);

      // 2. GPS Activity Route Polylines (if available)
      if (loc.routes && Array.isArray(loc.routes) && loc.routes.length > 0) {
        loc.routes.forEach(route => {
          if (route.coordinates && route.coordinates.length > 0) {
            route.coordinates.forEach(pt => bounds.push(pt));

            const polyline = L.polyline(route.coordinates, {
              color: '#0284c7',
              weight: 4.5,
              opacity: 0.92,
              lineCap: 'round',
              lineJoin: 'round',
              className: 'route-track-polyline'
            });

            const popupContent = `
              <div class="map-popup-card route-popup-card">
                <div class="text-xs font-bold text-primary mb-1">🗺️ GPS Aktivität (${loc.date})</div>
                <h4 class="font-bold text-sm mb-1">${route.title || 'GPS Route'}</h4>
                ${route.distance_km ? `<p class="text-xs text-muted">Distanz: ${route.distance_km.toFixed(2)} km</p>` : ''}
                ${route.elevation_gain_m ? `<p class="text-xs text-muted mb-2">Höhenmeter: +${Math.round(route.elevation_gain_m)} m</p>` : ''}
                <button class="btn btn-primary btn-xs w-full mt-2" onclick="jumpFromMapToReport('${loc.date}')">
                  Bericht öffnen
                </button>
              </div>
            `;
            polyline.bindPopup(popupContent);

            polyline.on('mouseover', function() {
              this.setStyle({ color: '#38bdf8', weight: 6.5, opacity: 1 });
            });
            polyline.on('mouseout', function() {
              this.setStyle({ color: '#0284c7', weight: 4.5, opacity: 0.92 });
            });

            mapRoutesGroup.addLayer(polyline);

            // Start & Finish markers
            const startPt = route.coordinates[0];
            const lastPt = route.coordinates[route.coordinates.length - 1];

            const startIcon = L.divIcon({
              className: 'custom-pin',
              html: '<div class="route-marker-pin route-marker-start" style="width:22px;height:22px;">S</div>',
              iconSize: [22, 22],
              iconAnchor: [11, 11]
            });
            const startMarker = L.marker(startPt, { icon: startIcon });
            startMarker.bindPopup(`<b>Start</b>: ${route.title || 'Start'}<br><button class="btn btn-primary btn-xs w-full mt-2" onclick="jumpFromMapToReport('${loc.date}')">Bericht öffnen</button>`);
            mapRoutesGroup.addLayer(startMarker);

            const finishIcon = L.divIcon({
              className: 'custom-pin',
              html: '<div class="route-marker-pin route-marker-finish" style="width:22px;height:22px;">Z</div>',
              iconSize: [22, 22],
              iconAnchor: [11, 11]
            });
            const finishMarker = L.marker(lastPt, { icon: finishIcon });
            finishMarker.bindPopup(`<b>Ziel</b>: ${route.title || 'Ziel'}<br><button class="btn btn-primary btn-xs w-full mt-2" onclick="jumpFromMapToReport('${loc.date}')">Bericht öffnen</button>`);
            mapRoutesGroup.addLayer(finishMarker);
          }
        });
      }
    });

    updateMapRoutesVisibility();

    if (bounds.length > 0) {
      mapInstance.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 });
    }
  } catch (err) {
    console.error('Error loading locations:', err);
  }
}

function fitMapBounds() {
  loadMapLocations();
}

function jumpFromMapToReport(dateStr) {
  switchMainView('report');
  selectDate(dateStr);
}

// --- Share Modal Logic ---

function resolvePublicShareUrl(shareUrl, token) {
  if (!token) return shareUrl;
  try {
    // Derive the base path prefix (e.g. '/memreport' if accessed via http://192.168.2.41:8125/memreport/viewer)
    const appBasePath = window.location.pathname.replace(/\/viewer.*$/, '');
    return `${window.location.origin}${appBasePath}/share/${token}`;
  } catch (e) {
    return shareUrl;
  }
}

function toggleShareAllCheckbox(checked) {
  const datesGroup = document.getElementById('share-dates-group');
  if (!datesGroup) return;
  if (checked) {
    datesGroup.style.opacity = '0.35';
    datesGroup.style.pointerEvents = 'none';
  } else {
    datesGroup.style.opacity = '1';
    datesGroup.style.pointerEvents = 'auto';
  }
}

function toggleEditShareAllCheckbox(checked) {
  const datesGroup = document.getElementById('edit-share-dates-group');
  if (!datesGroup) return;
  if (checked) {
    datesGroup.style.opacity = '0.35';
    datesGroup.style.pointerEvents = 'none';
  } else {
    datesGroup.style.opacity = '1';
    datesGroup.style.pointerEvents = 'auto';
  }
}

function openShareModal() {
  populateShareDatesChecklist();
  document.getElementById('share-result-box').classList.add('hidden');
  document.getElementById('share-title').value = '';
  const shareAllCb = document.getElementById('share-all-reports-checkbox');
  if (shareAllCb) {
    shareAllCb.checked = false;
    toggleShareAllCheckbox(false);
  }
  switchShareTab('create');
  document.getElementById('modal-share').classList.remove('hidden');
}

function closeShareModal() {
  document.getElementById('modal-share').classList.add('hidden');
}

function openShareCurrentDateModal() {
  openShareModal();
  switchShareTab('create');
  const shareAllCb = document.getElementById('share-all-reports-checkbox');
  if (shareAllCb) {
    shareAllCb.checked = false;
    toggleShareAllCheckbox(false);
  }
  selectCurrentDateOnly();
}

function switchShareTab(tab) {
  const createTab = document.getElementById('tab-share-create');
  const listTab = document.getElementById('tab-share-list');
  const createView = document.getElementById('share-view-create');
  const listView = document.getElementById('share-view-list');
  const editView = document.getElementById('share-view-edit');

  if (editView) editView.classList.add('hidden');

  if (tab === 'create') {
    createTab.classList.add('active');
    listTab.classList.remove('active');
    createView.classList.remove('hidden');
    listView.classList.add('hidden');
  } else {
    listTab.classList.add('active');
    createTab.classList.remove('active');
    listView.classList.remove('hidden');
    createView.classList.add('hidden');
    loadActiveShares();
  }
}

function populateShareDatesChecklist() {
  const container = document.getElementById('share-dates-checklist');
  container.innerHTML = '';

  const dates = Object.keys(reportsMap).sort().reverse();

  if (dates.length === 0) {
    container.innerHTML = '<span class="text-xs text-muted">Keine Berichte zum Teilen vorhanden</span>';
    return;
  }

  dates.forEach(d => {
    const label = document.createElement('label');
    label.className = 'date-check-item';
    label.innerHTML = `
      <input type="checkbox" value="${d}" class="share-date-checkbox" ${d === selectedDateStr ? 'checked' : ''} />
      <span>${d}</span>
      <span class="text-xs text-muted">(${reportsMap[d].content_type})</span>
    `;
    container.appendChild(label);
  });
}

function selectCurrentDateOnly() {
  document.querySelectorAll('.share-date-checkbox').forEach(cb => {
    cb.checked = (cb.value === selectedDateStr);
  });
}

function selectAllDates() {
  document.querySelectorAll('.share-date-checkbox').forEach(cb => {
    cb.checked = true;
  });
}

async function generateShareLink() {
  const shareAll = document.getElementById('share-all-reports-checkbox')?.checked || false;
  let selectedDates = [];
  if (!shareAll) {
    selectedDates = Array.from(document.querySelectorAll('.share-date-checkbox:checked')).map(cb => cb.value);
    if (selectedDates.length === 0) {
      alert('Bitte mindestens ein Datum auswählen oder "Alle Berichte teilen" aktivieren.');
      return;
    }
  }

  const title = document.getElementById('share-title').value.trim() || null;
  const expiryDays = parseInt(document.getElementById('share-expiry').value, 10);

  const payload = {
    dates: selectedDates,
    title: title,
    share_all: shareAll,
    expires_in_days: expiryDays > 0 ? expiryDays : null
  };

  try {
    const res = await fetch('/api/shares', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('Freigabe-Link konnte nicht erstellt werden');

    const data = await res.json();
    const finalUrl = resolvePublicShareUrl(data.share_url, data.token);
    document.getElementById('share-url-input').value = finalUrl;
    document.getElementById('share-open-link').href = finalUrl;
    document.getElementById('share-result-box').classList.remove('hidden');
  } catch (err) {
    alert(err.message);
  }
}

function copyShareUrl() {
  const input = document.getElementById('share-url-input');
  input.select();
  navigator.clipboard.writeText(input.value);
  const btn = document.getElementById('btn-copy-share');
  const original = btn.textContent;
  btn.textContent = 'Kopiert!';
  setTimeout(() => { btn.textContent = original; }, 2000);
}

let currentActiveShares = [];

async function loadActiveShares() {
  const container = document.getElementById('active-shares-container');
  container.innerHTML = '<div class="text-xs text-muted">Lade Freigaben...</div>';

  try {
    const res = await fetch('/api/shares');
    if (!res.ok) throw new Error('Konnte Freigaben nicht laden');
    const shares = await res.json();
    currentActiveShares = shares;

    if (shares.length === 0) {
      container.innerHTML = '<div class="text-xs text-muted">Keine aktiven Freigaben vorhanden</div>';
      return;
    }

    container.innerHTML = '';
    shares.forEach(s => {
      const finalUrl = resolvePublicShareUrl(s.share_url, s.token);
      const isShareAll = Boolean(s.share_all);
      const scopeBadge = isShareAll
        ? '<span class="inline-flex items-center text-[10px] bg-indigo-900/60 text-indigo-300 px-1.5 py-0.5 rounded font-medium border border-indigo-700/50">🌐 Alle Berichte (inkl. zukünftige)</span>'
        : `<span class="text-xs text-muted">${s.dates.length} Tage geteilt: ${s.dates.join(', ')}</span>`;

      const item = document.createElement('div');
      item.className = 'active-share-item';
      item.innerHTML = `
        <div class="flex-1 min-w-0 mr-2">
          <div class="flex items-center gap-2 mb-0.5">
            <p class="font-semibold text-xs truncate">${s.title || 'Unbenannte Freigabe'}</p>
            ${isShareAll ? scopeBadge : ''}
          </div>
          ${!isShareAll ? `<p class="text-xs text-muted mb-1">${scopeBadge}</p>` : ''}
          <a href="${finalUrl}" target="_blank" class="text-xs text-primary underline truncate block font-mono">${finalUrl}</a>
        </div>
        <div class="flex items-center gap-1.5 flex-shrink-0">
          <button class="btn btn-secondary btn-xs" onclick="openEditShare(${s.id})" title="Tage oder Titel bearbeiten">Bearbeiten</button>
          <button class="btn btn-danger btn-xs" onclick="revokeShare(${s.id})" title="Freigabe löschen">Widerrufen</button>
        </div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    container.innerHTML = `<div class="text-xs text-rose-400">${err.message}</div>`;
  }
}

function openEditShare(shareId) {
  const share = currentActiveShares.find(s => s.id === shareId);
  if (!share) return;

  document.getElementById('edit-share-id').value = share.id;
  document.getElementById('edit-share-title').value = share.title || '';

  const shareAllCb = document.getElementById('edit-share-all-checkbox');
  shareAllCb.checked = Boolean(share.share_all);
  toggleEditShareAllCheckbox(shareAllCb.checked);

  // Populate edit dates checklist
  const container = document.getElementById('edit-share-dates-checklist');
  container.innerHTML = '';
  const allDates = Object.keys(reportsMap).sort().reverse();

  if (allDates.length === 0) {
    container.innerHTML = '<span class="text-xs text-muted">Keine Berichte vorhanden</span>';
  } else {
    allDates.forEach(d => {
      const isChecked = share.dates.includes(d);
      const label = document.createElement('label');
      label.className = 'date-check-item';
      label.innerHTML = `
        <input type="checkbox" value="${d}" class="edit-share-date-checkbox" ${isChecked ? 'checked' : ''} />
        <span>${d}</span>
        <span class="text-xs text-muted">(${reportsMap[d].content_type})</span>
      `;
      container.appendChild(label);
    });
  }

  // Switch to edit view
  document.getElementById('share-view-list').classList.add('hidden');
  document.getElementById('share-view-create').classList.add('hidden');
  document.getElementById('share-view-edit').classList.remove('hidden');
}

function selectAllEditDates(selectAll) {
  document.querySelectorAll('.edit-share-date-checkbox').forEach(cb => {
    cb.checked = selectAll;
  });
}

async function saveShareEdit() {
  const shareId = parseInt(document.getElementById('edit-share-id').value, 10);
  if (!shareId) return;

  const title = document.getElementById('edit-share-title').value.trim() || null;
  const shareAll = document.getElementById('edit-share-all-checkbox').checked;

  let selectedDates = [];
  if (!shareAll) {
    selectedDates = Array.from(document.querySelectorAll('.edit-share-date-checkbox:checked')).map(cb => cb.value);
    if (selectedDates.length === 0) {
      alert('Bitte mindestens ein Datum auswählen oder "Alle Berichte teilen" aktivieren.');
      return;
    }
  }

  try {
    const res = await fetch(`/api/shares/${shareId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        share_all: shareAll,
        dates: selectedDates
      })
    });

    if (!res.ok) throw new Error('Änderungen konnten nicht gespeichert werden');

    // Return to list view and refresh
    switchShareTab('list');
  } catch (err) {
    alert(err.message);
  }
}

async function revokeShare(id) {
  if (!confirm('Möchtest du diese Freigabe wirklich widerrufen?')) return;
  try {
    const res = await fetch(`/api/shares/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Widerrufen fehlgeschlagen');
    await loadActiveShares();
  } catch (err) {
    alert(err.message);
  }
}

// --- Profile & Security Modal ---

function openProfileModal() {
  const currentUsername = document.getElementById('header-username').textContent.trim();
  document.getElementById('profile-username').value = currentUsername;
  document.getElementById('profile-new-password').value = '';
  document.getElementById('profile-confirm-password').value = '';
  document.getElementById('profile-current-password').value = '';

  const alertBox = document.getElementById('profile-alert');
  alertBox.classList.add('hidden');
  alertBox.textContent = '';

  const currentTheme = document.documentElement.classList.contains('light') ? 'light' : 'dark';
  const darkRadio = document.getElementById('profile-theme-dark');
  const lightRadio = document.getElementById('profile-theme-light');
  if (darkRadio && lightRadio) {
    if (currentTheme === 'light') lightRadio.checked = true;
    else darkRadio.checked = true;
  }

  document.getElementById('modal-profile').classList.remove('hidden');
}

function closeProfileModal() {
  document.getElementById('modal-profile').classList.add('hidden');
}

async function handleProfileSubmit(e) {
  e.preventDefault();

  const newUsername = document.getElementById('profile-username').value.trim();
  const newPassword = document.getElementById('profile-new-password').value;
  const confirmPassword = document.getElementById('profile-confirm-password').value;
  const currentPassword = document.getElementById('profile-current-password').value;

  const alertBox = document.getElementById('profile-alert');
  const saveBtn = document.getElementById('btn-save-profile');

  alertBox.classList.add('hidden');

  if (newPassword && newPassword !== confirmPassword) {
    alertBox.className = 'alert alert-error';
    alertBox.textContent = 'Die neuen Passwörter stimmen nicht überein.';
    alertBox.classList.remove('hidden');
    return;
  }

  saveBtn.disabled = true;

  const payload = {
    current_password: currentPassword,
    new_username: newUsername || null,
    new_password: newPassword || null,
  };

  try {
    const res = await fetch('/api/auth/me', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Aktualisierung fehlgeschlagen.');
    }

    // Update UI with new username
    document.getElementById('header-username').textContent = data.username;
    const avatarEl = document.getElementById('header-user-avatar');
    if (avatarEl && data.username.length > 0) {
      avatarEl.textContent = data.username[0].toUpperCase();
    }

    alertBox.className = 'alert';
    alertBox.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
    alertBox.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    alertBox.style.color = '#6ee7b7';
    alertBox.textContent = 'Profil erfolgreich aktualisiert!';
    alertBox.classList.remove('hidden');

    setTimeout(() => {
      closeProfileModal();
    }, 1200);
  } catch (err) {
    alertBox.className = 'alert alert-error';
    alertBox.textContent = err.message;
    alertBox.classList.remove('hidden');
  } finally {
    saveBtn.disabled = false;
  }
}

async function handleAdminCreateUser(e) {
  e.preventDefault();
  const usernameInput = document.getElementById('admin-new-username');
  const passwordInput = document.getElementById('admin-new-password');
  const isAdminInput = document.getElementById('admin-new-is-admin');
  const alertBox = document.getElementById('admin-create-alert');
  const btn = document.getElementById('btn-admin-create-user');

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const is_admin = isAdminInput.checked;

  alertBox.classList.add('hidden');
  btn.disabled = true;

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, is_admin })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Fehler beim Erstellen des Benutzers.');
    }

    alertBox.className = 'alert';
    alertBox.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
    alertBox.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    alertBox.style.color = '#6ee7b7';
    alertBox.textContent = `Benutzer "${data.username}" wurde erfolgreich erstellt!`;
    alertBox.classList.remove('hidden');

    usernameInput.value = '';
    passwordInput.value = '';
    isAdminInput.checked = false;
  } catch (err) {
    alertBox.className = 'alert alert-error';
    alertBox.textContent = err.message;
    alertBox.classList.remove('hidden');
  } finally {
    btn.disabled = false;
  }
}

// --- Auth Logout ---

async function logout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {
    console.error('Logout error:', e);
  }
  // Clear any potential cookies and navigate to /login
  window.location.href = '/logout';
}


function renderInteractiveComponents(container) {
  if (!container) return;

  // 1. Interactive Plotly Charts
  container.querySelectorAll("pre code.language-plotly").forEach((block) => {
    try {
      const rawJson = block.textContent.trim();
      const spec = JSON.parse(rawJson);
      const preEl = block.closest("pre");
      if (!preEl) return;

      const widget = document.createElement("div");
      widget.className = "interactive-plotly-widget";
      const plotId = "plotly-" + Math.random().toString(36).substring(2, 10);
      widget.id = plotId;
      preEl.parentNode.replaceChild(widget, preEl);

      const layout = spec.layout || {};
      layout.paper_bgcolor = layout.paper_bgcolor || "rgba(0,0,0,0)";
      layout.plot_bgcolor = layout.plot_bgcolor || "rgba(0,0,0,0)";
      layout.font = Object.assign({ color: "#f8fafc", family: "Inter, sans-serif" }, layout.font || {});
      layout.autosize = true;

      const config = Object.assign({ responsive: true, displayModeBar: true, displaylogo: false }, spec.config || {});

      if (window.Plotly) {
        Plotly.newPlot(widget, spec.data || [], layout, config);
      }
    } catch (err) {
      console.warn("Failed rendering interactive plotly widget:", err);
    }
  });

  // 2. Interactive Leaflet Route Maps
  container.querySelectorAll("pre code.language-leaflet, pre code.language-geojson").forEach((block) => {
    try {
      const rawJson = block.textContent.trim();
      const spec = JSON.parse(rawJson);
      const preEl = block.closest("pre");
      if (!preEl) return;

      const mapContainer = document.createElement("div");
      mapContainer.className = "interactive-map-widget";
      const mapId = "map-" + Math.random().toString(36).substring(2, 10);
      mapContainer.id = mapId;
      preEl.parentNode.replaceChild(mapContainer, preEl);

      if (!window.L) return;

      const map = L.map(mapId, {
        scrollWheelZoom: false,
        attributionControl: true
      }).setView([51.1657, 10.4515], 13);

      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
      }).addTo(map);

      let latLngs = [];

      if (spec.type === "FeatureCollection" || spec.type === "Feature" || spec.type === "LineString") {
        const geoLayer = L.geoJSON(spec, {
          style: {
            color: "#0284c7",
            weight: 5,
            opacity: 0.95
          }
        }).addTo(map);
        try {
          map.fitBounds(geoLayer.getBounds(), { padding: [35, 35] });
        } catch (e) {}
      } else if (spec.coordinates && Array.isArray(spec.coordinates) && spec.coordinates.length > 0) {
        latLngs = spec.coordinates.map(pt => [pt[0], pt[1]]);
        const polyline = L.polyline(latLngs, {
          color: "#0284c7",
          weight: 4.5,
          opacity: 0.95,
          lineJoin: "round"
        }).addTo(map);

        const startIcon = L.divIcon({
          className: "custom-pin",
          html: "<div class=\"route-marker-pin route-marker-start\" style=\"width:24px;height:24px;\">S</div>",
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });
        L.marker(latLngs[0], { icon: startIcon })
          .addTo(map)
          .bindPopup(`<b>Start</b><br>${spec.title || "Startpunkt"}`);

        const finishIcon = L.divIcon({
          className: "custom-pin",
          html: "<div class=\"route-marker-pin route-marker-finish\" style=\"width:24px;height:24px;\">Z</div>",
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });
        const lastPt = latLngs[latLngs.length - 1];

        let distKm = spec.distance_km;
        if ((distKm === null || distKm === undefined) && latLngs.length > 1) {
          let totalMeters = 0;
          for (let i = 1; i < latLngs.length; i++) {
            totalMeters += L.latLng(latLngs[i - 1][0], latLngs[i - 1][1]).distanceTo(
              L.latLng(latLngs[i][0], latLngs[i][1])
            );
          }
          distKm = totalMeters / 1000;
        }

        let finishMsg = `<b>Ziel</b>`;
        if (distKm) finishMsg += `<br>Distanz: ${distKm.toFixed(2)} km`;
        if (spec.elevation_gain_m) finishMsg += `<br>Höhenmeter: +${Math.round(spec.elevation_gain_m)} m`;
        L.marker(lastPt, { icon: finishIcon })
          .addTo(map)
          .bindPopup(finishMsg);

        map.fitBounds(polyline.getBounds(), { padding: [35, 35] });
      }

      setTimeout(() => {
        map.invalidateSize();
      }, 300);
    } catch (err) {
      console.warn("Failed rendering interactive map widget:", err);
    }
  });
}

// --- Theme Switcher (Light / Dark) ---

async function initTheme() {
  let theme = 'dark';
  try {
    theme = localStorage.getItem('memreport-theme') || 'dark';
  } catch (e) {}
  applyTheme(theme);

  // Sync with user profile from backend
  try {
    const res = await fetch('/api/auth/me');
    if (res.ok) {
      const user = await res.json();
      if (user.theme && user.theme !== theme) {
        applyTheme(user.theme);
      }
    }
  } catch (e) {}
}

function applyTheme(theme) {
  const html = document.documentElement;
  const moonIcon = document.querySelector('.theme-icon-moon');
  const sunIcon = document.querySelector('.theme-icon-sun');
  const themeStatusText = document.getElementById('theme-status-text');

  if (theme === 'light') {
    html.classList.remove('dark');
    html.classList.add('light');
    if (moonIcon) moonIcon.classList.add('hidden');
    if (sunIcon) sunIcon.classList.remove('hidden');
    if (themeStatusText) themeStatusText.textContent = 'Design: Hell';
  } else {
    html.classList.remove('light');
    html.classList.add('dark');
    if (moonIcon) moonIcon.classList.remove('hidden');
    if (sunIcon) sunIcon.classList.add('hidden');
    if (themeStatusText) themeStatusText.textContent = 'Design: Dunkel';
  }

  try {
    localStorage.setItem('memreport-theme', theme);
  } catch (e) {}

  const darkRadio = document.getElementById('profile-theme-dark');
  const lightRadio = document.getElementById('profile-theme-light');
  if (darkRadio && lightRadio) {
    if (theme === 'light') lightRadio.checked = true;
    else darkRadio.checked = true;
  }

  if (window.mapInstance) {
    window.mapInstance.invalidateSize();
  }
}

function setTheme(theme) {
  if (theme !== 'light' && theme !== 'dark') return;
  applyTheme(theme);
  // Persist to user profile backend
  fetch('/api/auth/me/theme', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme })
  }).catch(err => console.debug('Could not save theme to profile:', err));
}

function toggleTheme() {
  const currentTheme = document.documentElement.classList.contains('light') ? 'light' : 'dark';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  setTheme(newTheme);
}

function toggleProfileDropdown(event) {
  if (event) {
    event.stopPropagation();
  }
  const menu = document.getElementById('profile-dropdown-menu');
  const container = document.querySelector('.profile-dropdown-container');
  if (!menu) return;
  const isHidden = menu.classList.contains('hidden');
  if (isHidden) {
    menu.classList.remove('hidden');
    if (container) container.classList.add('open');
  } else {
    menu.classList.add('hidden');
    if (container) container.classList.remove('open');
  }
}

function closeProfileDropdown() {
  const menu = document.getElementById('profile-dropdown-menu');
  const container = document.querySelector('.profile-dropdown-container');
  if (menu && !menu.classList.contains('hidden')) {
    menu.classList.add('hidden');
    if (container) container.classList.remove('open');
  }
}

document.addEventListener('click', (e) => {
  const container = document.querySelector('.profile-dropdown-container');
  if (container && !container.contains(e.target)) {
    closeProfileDropdown();
  }
});

// --- AI Review Modal Logic ---

function openReviewModal() {
  if (!currentReport) {
    alert('Kein Bericht zum Reviewen vorhanden.');
    return;
  }
  document.getElementById('review-feedback-textarea').value = '';
  document.getElementById('review-error-alert').classList.add('hidden');
  document.getElementById('review-progress').classList.add('hidden');
  document.getElementById('btn-submit-review').disabled = false;
  document.getElementById('review-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('review-feedback-textarea').focus(), 100);
}

function closeReviewModal() {
  document.getElementById('review-modal').classList.add('hidden');
}

function handleReviewModalOverlayClick(e) {
  if (e.target === e.currentTarget) {
    closeReviewModal();
  }
}

async function submitReview() {
  const feedback = document.getElementById('review-feedback-textarea').value.trim();
  if (!feedback) {
    document.getElementById('review-feedback-textarea').focus();
    return;
  }

  const errorAlert = document.getElementById('review-error-alert');
  const progress = document.getElementById('review-progress');
  const submitBtn = document.getElementById('btn-submit-review');

  errorAlert.classList.add('hidden');
  progress.classList.remove('hidden');
  submitBtn.disabled = true;

  try {
    const res = await fetch(`/api/reports/${selectedDateStr}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback: feedback })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Unbekannter Fehler' }));
      throw new Error(errData.detail || `HTTP ${res.status}`);
    }

    const updatedReport = await res.json();
    currentReport = updatedReport;
    showReportContent(currentReport);
    await loadReportsList();
    renderCalendar();
    closeReviewModal();

  } catch (err) {
    errorAlert.textContent = err.message;
    errorAlert.classList.remove('hidden');
  } finally {
    progress.classList.add('hidden');
    submitBtn.disabled = false;
  }
}
