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
let mapMarkersGroup = null;

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
  await loadReportsList();
  renderCalendar();
  await loadReportForDate(selectedDateStr);
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
    div.className = `report-item ${item.date === selectedDateStr ? 'active' : ''}`;
    div.id = `report-item-${item.date}`;
    div.onclick = () => selectDate(item.date);

    const hasGpsIcon = item.has_location
      ? `<span title="GPS hinterlegt" class="text-amber-400">📍</span>`
      : '';

    div.innerHTML = `
      <div class="report-item-date">
        <span>${item.date}</span>
        ${hasGpsIcon}
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

function renderCalendar() {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
  ];
  document.getElementById('calendar-month-year').textContent = `${monthNames[month]} ${year}`;

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
    const hasReport = !!reportsMap[dateStr];
    const hasGps = hasReport && reportsMap[dateStr].has_location;

    if (hasReport || hasGps) {
      const ind = document.createElement('div');
      ind.className = 'day-indicators';
      if (hasReport) {
        const dot = document.createElement('span');
        dot.className = 'indicator-dot dot-report';
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

function jumpToToday() {
  currentDate = new Date();
  selectDate(formatDate(currentDate));
}

async function selectDate(dateStr) {
  selectedDateStr = dateStr;
  const [y, m, d] = dateStr.split('-').map(Number);
  currentDate = new Date(y, m - 1, d);

  renderCalendar();

  // Update active item in sidebar
  document.querySelectorAll('.report-item').forEach(el => el.classList.remove('active'));
  const activeItem = document.getElementById(`report-item-${dateStr}`);
  if (activeItem) activeItem.classList.add('active');

  if (isEditMode) cancelEditMode();
  await loadReportForDate(dateStr);
}

// --- Report Loading & Rendering ---

async function loadReportForDate(dateStr) {
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
}

function showReportContent(report) {
  document.getElementById('report-empty-state').classList.add('hidden');
  document.getElementById('report-editor-view').classList.add('hidden');
  document.getElementById('report-rendered-view').classList.remove('hidden');
  document.getElementById('report-raw-view').classList.add('hidden');
  document.getElementById('btn-toggle-raw').disabled = false;

  renderMarkdownAndHtml(report.content, document.getElementById('rendered-content'));
  document.getElementById('raw-content-code').textContent = report.content;
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

  // Highlight.js
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

  if (report && report.latitude && report.longitude) {
    badge.classList.add('has-location');
    const label = report.location_name || `${report.latitude.toFixed(4)}, ${report.longitude.toFixed(4)}`;
    text.textContent = label;
  } else {
    badge.classList.remove('has-location');
    text.textContent = 'GPS hinzufügen';
  }
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
    mapInstance = L.map('leaflet-map-container').setView([51.1657, 10.4515], 6);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 19
    }).addTo(mapInstance);

    mapMarkersGroup = L.layerGroup().addTo(mapInstance);

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

async function loadMapLocations() {
  if (!mapMarkersGroup) return;
  mapMarkersGroup.clearLayers();

  try {
    const res = await fetch('/api/locations');
    if (!res.ok) throw new Error('Fehler beim Laden der Standorte');
    const locations = await res.json();

    const bounds = [];

    locations.forEach(loc => {
      bounds.push([loc.latitude, loc.longitude]);

      const customIcon = L.divIcon({
        className: 'custom-map-bubble',
        html: `
          <div class="map-bubble-inner">
            <span class="bubble-dot"></span>
            <span class="bubble-date">${loc.date.slice(5)}</span>
          </div>
        `,
        iconSize: [80, 32],
        iconAnchor: [40, 16]
      });

      const marker = L.marker([loc.latitude, loc.longitude], { icon: customIcon });
      marker.bindPopup(`
        <div class="map-popup-card">
          <h4 class="font-bold text-sm mb-1">${loc.date}</h4>
          <p class="text-xs text-muted mb-2">${loc.location_name || 'Standort'}</p>
          <button class="btn btn-primary btn-xs w-full" onclick="jumpFromMapToReport('${loc.date}')">
            Bericht öffnen
          </button>
        </div>
      `);
      mapMarkersGroup.addLayer(marker);
    });

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

let currentShareTab = 'create';

function openShareModal() {
  populateShareDatesChecklist();
  document.getElementById('share-result-box').classList.add('hidden');
  document.getElementById('modal-share').classList.remove('hidden');
  switchShareTab('create');
}

function openShareCurrentDateModal() {
  openShareModal();
  selectCurrentDateOnly();
}

function closeShareModal() {
  document.getElementById('modal-share').classList.add('hidden');
}

function switchShareTab(tab) {
  currentShareTab = tab;
  const createTab = document.getElementById('tab-share-create');
  const listTab = document.getElementById('tab-share-list');
  const createView = document.getElementById('share-view-create');
  const listView = document.getElementById('share-view-list');

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
  const selectedDates = Array.from(document.querySelectorAll('.share-date-checkbox:checked')).map(cb => cb.value);
  if (selectedDates.length === 0) {
    alert('Bitte mindestens ein Datum auswählen');
    return;
  }

  const title = document.getElementById('share-title').value.trim() || null;
  const expiryDays = parseInt(document.getElementById('share-expiry').value, 10);

  const payload = {
    dates: selectedDates,
    title: title,
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
    document.getElementById('share-url-input').value = data.share_url;
    document.getElementById('share-open-link').href = data.share_url;
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

async function loadActiveShares() {
  const container = document.getElementById('active-shares-container');
  container.innerHTML = '<div class="text-xs text-muted">Lade Freigaben...</div>';

  try {
    const res = await fetch('/api/shares');
    if (!res.ok) throw new Error('Konnte Freigaben nicht laden');
    const shares = await res.json();

    if (shares.length === 0) {
      container.innerHTML = '<div class="text-xs text-muted">Keine aktiven Freigaben vorhanden</div>';
      return;
    }

    container.innerHTML = '';
    shares.forEach(s => {
      const item = document.createElement('div');
      item.className = 'active-share-item';
      item.innerHTML = `
        <div class="flex-1 min-w-0 mr-2">
          <p class="font-semibold text-xs truncate">${s.title || 'Unbenannte Freigabe'}</p>
          <p class="text-xs text-muted">${s.dates.length} Tage geteilt: ${s.dates.join(', ')}</p>
          <a href="${s.share_url}" target="_blank" class="text-xs text-primary underline truncate block">${s.share_url}</a>
        </div>
        <button class="btn btn-danger btn-xs" onclick="revokeShare(${s.id})">Widerrufen</button>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    container.innerHTML = `<div class="text-xs text-rose-400">${err.message}</div>`;
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

// --- Auth Logout ---

async function logout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {}
  window.location.href = '/login';
}
