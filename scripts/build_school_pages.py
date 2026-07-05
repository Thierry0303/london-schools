<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>London Schools & Homes</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --ink: #111827; --ink-2: #374151; --ink-3: #6B7280;
      --gold: #D4A843; --gold-lt: #FDF6E3; --gold-md: #F5E6B8;
      --green: #059669; --green-lt: #ECFDF5;
      --blue: #2563EB; --blue-lt: #EFF6FF;
      --amber: #D97706; --amber-lt: #FFFBEB;
      --red: #DC2626; --red-lt: #FEF2F2;
      --bg: #F9FAFB; --surface: #FFFFFF; --border: #E5E7EB; --border-2: #D1D5DB;
      --radius: 10px; --radius-lg: 16px;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { font-size: 15px; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--ink); min-height: 100vh; }

    /* ── Top bar ── */
    .topbar { background: var(--ink); height: 56px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; position: sticky; top: 0; z-index: 900; }
    .topbar-logo { display: flex; align-items: center; gap: 10px; }
    .topbar-logo-mark { width: 32px; height: 32px; background: var(--gold); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-family: 'Playfair Display', serif; font-weight: 900; font-size: 1rem; color: var(--ink); flex-shrink: 0; }
    .topbar-logo-text { font-family: 'Playfair Display', serif; font-weight: 700; font-size: 1.05rem; color: white; letter-spacing: -0.01em; }
    .topbar-logo-text span { color: var(--gold); }
    .topbar-nav { display: flex; gap: 2px; }
    .topbar-nav-btn { display: flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 7px; border: none; background: transparent; color: rgba(255,255,255,0.6); font-family: 'Inter', sans-serif; font-size: 0.82rem; font-weight: 500; cursor: pointer; transition: all 0.15s; }
    .topbar-nav-btn svg { width: 15px; height: 15px; opacity: 0.7; }
    .topbar-nav-btn:hover { background: rgba(255,255,255,0.08); color: white; }
    .topbar-nav-btn.active { background: var(--gold); color: var(--ink); font-weight: 600; }
    .topbar-nav-btn.active svg { opacity: 1; }

    /* ── Hero ── */
    .hero { background: var(--ink); color: white; padding: 48px 24px 40px; }
    .hero-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr auto; gap: 32px; align-items: center; }
    .hero-eyebrow { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--gold); margin-bottom: 10px; }
    .hero h1 { font-family: 'Playfair Display', serif; font-size: clamp(1.8rem, 4vw, 3rem); font-weight: 900; line-height: 1.08; margin-bottom: 10px; }
    .hero h1 em { font-style: italic; color: var(--gold); }
    .hero-sub { font-size: 0.9rem; color: rgba(255,255,255,0.55); line-height: 1.65; max-width: 480px; }
    .hero-stats { display: flex; gap: 0; flex-shrink: 0; background: rgba(255,255,255,0.06); border-radius: var(--radius); border: 1px solid rgba(255,255,255,0.1); overflow: hidden; }
    .hero-stat { padding: 18px 24px; text-align: center; border-right: 1px solid rgba(255,255,255,0.08); }
    .hero-stat:last-child { border-right: none; }
    .hero-stat-num { font-family: 'Playfair Display', serif; font-size: 1.8rem; font-weight: 700; color: var(--gold); line-height: 1; }
    .hero-stat-label { font-size: 0.65rem; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px; }

    /* ── Main layout ── */
    .main { max-width: 1200px; margin: 0 auto; padding: 28px 24px; }

    /* ── Filter bar ── */
    .filter-bar { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; }
    .fgroup { display: flex; flex-direction: column; gap: 4px; }
    .flabel { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-3); }
    .fsearch { position: relative; flex: 1; min-width: 200px; }
    .fsearch input { width: 100%; padding: 8px 12px 8px 34px; border: 1.5px solid var(--border); border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 0.88rem; color: var(--ink); background: var(--bg); outline: none; transition: border-color 0.2s; }
    .fsearch input:focus { border-color: var(--gold); background: white; }
    .fsearch-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--ink-3); pointer-events: none; }
    select { padding: 8px 28px 8px 10px; border: 1.5px solid var(--border); border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 0.85rem; background: var(--bg); color: var(--ink); cursor: pointer; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='11' height='7' viewBox='0 0 11 7'%3E%3Cpath d='M1 1l4.5 4.5L10 1' stroke='%236B7280' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 9px center; outline: none; transition: border-color 0.2s; min-width: 140px; }
    select:focus { border-color: var(--gold); background-color: white; }
    .clear-btn { padding: 8px 14px; background: transparent; border: 1.5px solid var(--border); border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 0.82rem; color: var(--ink-3); cursor: pointer; transition: all 0.15s; white-space: nowrap; align-self: flex-end; }
    .clear-btn:hover { border-color: var(--red); color: var(--red); background: var(--red-lt); }

    /* ── Results header ── */
    .results-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .results-count { font-size: 0.85rem; color: var(--ink-3); }
    .results-count strong { color: var(--ink); font-weight: 600; }
    .view-toggle { display: flex; gap: 2px; background: var(--border); border-radius: 8px; padding: 3px; }
    .view-btn { width: 30px; height: 26px; background: transparent; border: none; border-radius: 6px; cursor: pointer; color: var(--ink-3); font-size: 0.9rem; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
    .view-btn.active { background: white; color: var(--ink); }

    /* ── School grid ── */
    .school-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; }
    .school-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; cursor: pointer; transition: all 0.18s; position: relative; overflow: hidden; }
    .school-card::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--band-color, var(--border)); }
    .school-card:hover { border-color: var(--gold); box-shadow: 0 4px 20px rgba(0,0,0,0.08); transform: translateY(-1px); }
    .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
    .card-phase { font-size: 0.67rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-3); background: var(--bg); padding: 3px 7px; border-radius: 4px; border: 1px solid var(--border); }
    .card-name { font-family: 'Playfair Display', serif; font-size: 1rem; font-weight: 700; line-height: 1.3; margin-bottom: 4px; }
    .card-la { font-size: 0.77rem; color: var(--ink-3); margin-bottom: 12px; }
    .card-rating-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .card-rating-track { flex: 1; background: var(--bg); border-radius: 4px; height: 5px; overflow: hidden; border: 1px solid var(--border); }
    .card-rating-fill { height: 100%; border-radius: 4px; }
    .card-rating-label { font-size: 0.72rem; font-weight: 600; min-width: 100px; text-align: right; }
    .card-pills { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 12px; }
    .pill { font-size: 0.68rem; padding: 3px 8px; border-radius: 20px; font-weight: 500; border: 1px solid transparent; }
    .pill-o { background: var(--green-lt); color: var(--green); border-color: #A7F3D0; }
    .pill-g { background: var(--blue-lt); color: var(--blue); border-color: #BFDBFE; }
    .pill-r { background: var(--amber-lt); color: var(--amber); border-color: #FDE68A; }
    .pill-i { background: var(--red-lt); color: var(--red); border-color: #FECACA; }
    .pill-u { background: var(--bg); color: var(--ink-3); border-color: var(--border); }
    .card-meta { display: flex; gap: 12px; font-size: 0.74rem; color: var(--ink-3); padding-top: 10px; border-top: 1px solid var(--bg); flex-wrap: wrap; }

    /* ── School table ── */
    .school-table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); font-size: 0.84rem; }
    .school-table th { background: var(--ink); color: rgba(255,255,255,0.8); padding: 11px 14px; text-align: left; font-weight: 500; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.09em; }
    .school-table td { padding: 11px 14px; border-bottom: 1px solid var(--bg); vertical-align: middle; }
    .school-table tr:last-child td { border-bottom: none; }
    .school-table tr:hover td { background: var(--gold-lt); cursor: pointer; }
    .rank-num { font-family: 'Playfair Display', serif; font-weight: 700; color: var(--gold); }
    .band-chip { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 20px; font-size: 0.68rem; font-weight: 600; }

    /* ── Map ── */
    .map-wrap { border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); }
    #school-map { height: 560px; width: 100%; }
    .map-legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.75rem; color: var(--ink-3); margin-top: 12px; align-items: center; }
    .map-legend-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 5px; }

    /* ── Detail panel ── */
    .detail-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 2000; display: flex; justify-content: flex-end; animation: fadeIn 0.15s; }
    @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
    @keyframes slideIn { from { transform: translateX(100%) } to { transform: translateX(0) } }
    .detail-panel { width: 100%; max-width: 520px; background: var(--surface); height: 100%; overflow-y: auto; animation: slideIn 0.22s cubic-bezier(0.25,0.46,0.45,0.94); border-left: 1px solid var(--border); }
    .detail-header { background: var(--ink); color: white; padding: 24px 24px 20px; position: relative; }
    .detail-close { position: absolute; top: 16px; right: 16px; background: rgba(255,255,255,0.1); border: none; color: white; width: 32px; height: 32px; border-radius: 8px; cursor: pointer; font-size: 1rem; display: flex; align-items: center; justify-content: center; transition: background 0.15s; }
    .detail-close:hover { background: rgba(255,255,255,0.2); }
    .detail-phase-tag { font-size: 0.67rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.12em; color: var(--gold); margin-bottom: 7px; }
    .detail-name { font-family: 'Playfair Display', serif; font-size: 1.5rem; font-weight: 900; line-height: 1.15; margin-bottom: 5px; }
    .detail-la { font-size: 0.82rem; color: rgba(255,255,255,0.5); }
    .detail-score-row { display: flex; gap: 10px; margin-top: 18px; }
    .detail-score-box { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; text-align: center; flex: 1; }
    .detail-score-val { font-family: 'Playfair Display', serif; font-size: 1.6rem; font-weight: 700; color: var(--gold); line-height: 1; }
    .detail-score-desc { font-size: 0.63rem; text-transform: uppercase; letter-spacing: 0.09em; color: rgba(255,255,255,0.4); margin-top: 4px; }
    .detail-body { padding: 20px 24px; }
    .detail-section { margin-bottom: 20px; }
    .detail-section-title { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-3); margin-bottom: 10px; padding-bottom: 7px; border-bottom: 1px solid var(--border); }
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .detail-field { display: flex; flex-direction: column; gap: 2px; padding: 8px; background: var(--bg); border-radius: 7px; }
    .detail-field-label { font-size: 0.65rem; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.07em; }
    .detail-field-val { font-size: 0.85rem; font-weight: 500; color: var(--ink); }
    .rating-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
    .rating-label { font-size: 0.77rem; color: var(--ink-2); width: 160px; flex-shrink: 0; }
    .rating-bar-wrap { flex: 1; background: var(--bg); border-radius: 4px; height: 6px; overflow: hidden; border: 1px solid var(--border); }
    .rating-bar-fill { height: 100%; border-radius: 4px; }
    .rating-chip { font-size: 0.67rem; font-weight: 600; width: 110px; text-align: right; }

    /* ── Stats ── */
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; }
    .stat-card-num { font-family: 'Playfair Display', serif; font-size: 1.9rem; font-weight: 700; color: var(--ink); line-height: 1; margin-bottom: 4px; }
    .stat-card-label { font-size: 0.7rem; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.07em; }
    .chart-section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; margin-bottom: 14px; }
    .chart-title { font-family: 'Playfair Display', serif; font-size: 0.98rem; font-weight: 700; margin-bottom: 14px; }
    .bar-chart-row { display: flex; align-items: center; gap: 10px; margin-bottom: 7px; }
    .bar-chart-label { font-size: 0.77rem; width: 160px; flex-shrink: 0; color: var(--ink-2); }
    .bar-chart-wrap { flex: 1; background: var(--bg); border-radius: 3px; height: 18px; overflow: hidden; border: 1px solid var(--border); }
    .bar-chart-fill { height: 100%; border-radius: 3px; display: flex; align-items: center; padding-left: 7px; font-size: 0.68rem; font-weight: 600; color: white; min-width: 18px; }
    .bar-chart-count { font-size: 0.75rem; color: var(--ink-3); width: 30px; text-align: right; }

    /* ── Pagination ── */
    .pagination { display: flex; justify-content: center; align-items: center; gap: 5px; margin-top: 28px; }
    .page-btn { min-width: 32px; height: 32px; border: 1.5px solid var(--border); border-radius: 7px; background: var(--surface); cursor: pointer; font-family: 'Inter', sans-serif; font-size: 0.8rem; color: var(--ink); transition: all 0.15s; display: flex; align-items: center; justify-content: center; padding: 0 8px; }
    .page-btn.active { background: var(--ink); color: white; border-color: var(--ink); font-weight: 600; }
    .page-btn:hover:not(.active):not(:disabled) { border-color: var(--gold); color: var(--gold); }
    .page-btn:disabled { opacity: 0.3; cursor: not-allowed; }

    /* ── Loading / Empty ── */
    .loading { display: flex; align-items: center; justify-content: center; padding: 80px; font-size: 0.88rem; color: var(--ink-3); gap: 10px; }
    .spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--gold); border-radius: 50%; animation: spin 0.65s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg) } }
    .empty-state { text-align: center; padding: 60px; color: var(--ink-3); }
    .empty-state h3 { font-family: 'Playfair Display', serif; font-size: 1.2rem; margin-bottom: 8px; color: var(--ink-2); }

    /* ── Property view ── */
    .pv-layout { display: grid; grid-template-columns: 300px 1fr; gap: 20px; align-items: start; }
    .pv-sidebar { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 20px; position: sticky; top: 76px; }
    .pv-sidebar-title { font-family: 'Playfair Display', serif; font-size: 1.05rem; font-weight: 700; margin-bottom: 4px; }
    .pv-sidebar-sub { font-size: 0.77rem; color: var(--ink-3); line-height: 1.5; margin-bottom: 18px; }
    .pv-field { margin-bottom: 14px; }
    .pv-field-label { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-3); margin-bottom: 5px; }
    .pv-input { width: 100%; padding: 9px 12px; border: 1.5px solid var(--border); border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 0.85rem; color: var(--ink); background: var(--bg); outline: none; transition: border-color 0.2s; }
    .pv-input:focus { border-color: var(--gold); background: white; }
    .pv-input:disabled { opacity: 0.5; }
    .pv-select { width: 100%; padding: 9px 28px 9px 10px; border: 1.5px solid var(--border); border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 0.85rem; background: var(--bg); color: var(--ink); cursor: pointer; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='11' height='7' viewBox='0 0 11 7'%3E%3Cpath d='M1 1l4.5 4.5L10 1' stroke='%236B7280' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 9px center; outline: none; transition: border-color 0.2s; }
    .pv-select:focus { border-color: var(--gold); background-color: white; }
    .pv-divider { height: 1px; background: var(--border); margin: 16px 0; }
    .pv-section-label { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-3); margin-bottom: 10px; }
    .pv-chips { display: flex; flex-direction: column; gap: 6px; }
    .pv-chip { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1.5px solid var(--border); border-radius: 8px; cursor: pointer; transition: all 0.15s; background: var(--bg); }
    .pv-chip.on { border-color: var(--gold); background: var(--gold-lt); }
    .pv-chip-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .pv-chip-text { font-size: 0.8rem; font-weight: 500; color: var(--ink-2); }
    .pv-chip.on .pv-chip-text { color: var(--ink); }
    .pv-chip-check { margin-left: auto; font-size: 0.75rem; color: var(--gold); font-weight: 700; opacity: 0; }
    .pv-chip.on .pv-chip-check { opacity: 1; }
    .pv-search-btn { width: 100%; padding: 11px; background: var(--ink); color: var(--gold); border: none; border-radius: 9px; font-family: 'Playfair Display', serif; font-size: 0.95rem; font-weight: 700; cursor: pointer; transition: background 0.2s; margin-top: 16px; letter-spacing: 0.02em; }
    .pv-search-btn:hover { background: #1f2937; }
    .pv-search-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .pv-main { min-width: 0; }
    .pv-status { font-size: 0.8rem; color: var(--ink-3); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
    .pv-spinner { width: 13px; height: 13px; border: 2px solid var(--border); border-top-color: var(--gold); border-radius: 50%; animation: spin 0.65s linear infinite; flex-shrink: 0; }
    .pv-error { background: var(--red-lt); color: var(--red); border: 1px solid #FECACA; border-radius: 8px; padding: 10px 14px; font-size: 0.82rem; margin-bottom: 14px; }
    .pv-schools-found { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 16px; margin-bottom: 16px; }
    .pv-sf-label { font-size: 0.63rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-3); margin-bottom: 9px; }
    .pv-sf-list { display: flex; flex-wrap: wrap; gap: 7px; }
    .pv-sf-badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 20px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--border); background: var(--bg); color: var(--ink-2); }
    .pv-sf-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
    .pv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
    .pv-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; transition: all 0.18s; }
    .pv-card:hover { border-color: var(--gold); box-shadow: 0 4px 18px rgba(0,0,0,0.07); transform: translateY(-1px); }
    .pv-card-thumb { width: 100%; height: 140px; background: var(--bg); display: flex; align-items: center; justify-content: center; font-size: 1.8rem; overflow: hidden; position: relative; }
    .pv-card-thumb img { width: 100%; height: 100%; object-fit: cover; }
    .pv-card-tenure { position: absolute; top: 9px; left: 9px; background: var(--ink); color: var(--gold); font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; padding: 3px 8px; border-radius: 5px; }
    .pv-card-save { position: absolute; top: 9px; right: 9px; width: 28px; height: 28px; border-radius: 50%; background: white; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 0.85rem; transition: all 0.15s; }
    .pv-card-save.saved { background: var(--gold); border-color: var(--gold); }
    .pv-card-body { padding: 13px; }
    .pv-price { font-family: 'Playfair Display', serif; font-size: 1.12rem; font-weight: 700; color: var(--ink); margin-bottom: 3px; }
    .pv-address { font-size: 0.75rem; color: var(--ink-3); margin-bottom: 9px; line-height: 1.4; }
    .pv-pills { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 9px; }
    .pv-pill { font-size: 0.67rem; padding: 2px 8px; border-radius: 20px; border: 1px solid var(--border); color: var(--ink-3); background: var(--bg); }
    .pv-schools { border-top: 1px solid var(--bg); padding-top: 9px; }
    .pv-school-row { display: flex; align-items: flex-start; gap: 7px; padding: 4px 0; font-size: 0.73rem; }
    .pv-school-row + .pv-school-row { border-top: 1px solid var(--bg); }
    .pv-s-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 3px; }
    .pv-s-name { font-weight: 600; color: var(--ink-2); }
    .pv-s-detail { color: var(--ink-3); font-size: 0.68rem; }
    .pv-cta { display: flex; gap: 7px; margin-top: 11px; }
    .pv-btn-ghost { flex: 1; padding: 8px; font-size: 0.75rem; font-family: 'Inter', sans-serif; border: 1.5px solid var(--border); border-radius: 7px; background: var(--bg); cursor: pointer; color: var(--ink-2); font-weight: 500; transition: all 0.15s; }
    .pv-btn-ghost:hover { border-color: var(--gold); color: var(--ink); }
    .pv-btn-solid { flex: 1; padding: 8px; font-size: 0.75rem; font-family: 'Inter', sans-serif; border: none; border-radius: 7px; background: var(--ink); color: var(--gold); cursor: pointer; font-weight: 600; transition: background 0.15s; }
    .pv-btn-solid:hover { background: #1f2937; }
    .pv-empty { text-align: center; padding: 60px 20px; color: var(--ink-3); grid-column: 1/-1; }
    .pv-empty-icon { font-size: 2.5rem; margin-bottom: 12px; }
    .pv-empty h3 { font-family: 'Playfair Display', serif; font-size: 1.1rem; color: var(--ink-2); margin-bottom: 7px; }
    .pv-hero { background: var(--ink); border-radius: var(--radius-lg); padding: 28px; margin-bottom: 16px; color: white; }
    .pv-hero-tag { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.12em; color: var(--gold); margin-bottom: 8px; }
    .pv-hero-title { font-family: 'Playfair Display', serif; font-size: 1.35rem; font-weight: 700; margin-bottom: 6px; }
    .pv-hero-sub { font-size: 0.8rem; color: rgba(255,255,255,0.55); line-height: 1.5; }

    /* ── Responsive ── */
    @media (max-width: 900px) {
      .pv-layout { grid-template-columns: 1fr; }
      .pv-sidebar { position: static; }
      .hero-inner { grid-template-columns: 1fr; }
      .hero-stats { display: none; }
    }
    @media (max-width: 640px) {
      .topbar { padding: 0 14px; }
      .topbar-nav-btn span { display: none; }
      .main { padding: 16px 14px; }
      .hero { padding: 28px 14px; }
      .filter-bar { gap: 8px; }
      .school-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const { useState, useEffect, useMemo, useRef, useCallback } = React;

const API_BASE = 'http://localhost:8000';
const PROP_API = 'https://london-school-model.vercel.app/api';
const JSON_FALLBACK = './schools.json';

const BAND_COLORS = { Outstanding:'#059669', Good:'#2563EB', 'Requires improvement':'#D97706', Inadequate:'#DC2626', Unknown:'#9CA3AF' };
const BAND_BG    = { Outstanding:'#ECFDF5', Good:'#EFF6FF', 'Requires improvement':'#FFFBEB', Inadequate:'#FEF2F2', Unknown:'#F9FAFB' };
const RATING_MAP   = { 1:'Outstanding', 2:'Good', 3:'Requires improvement', 4:'Inadequate' };
const RATING_SCORES= { 1:100, 2:80, 3:40, 4:0 };

function BandChip({ band }) {
  const c = BAND_COLORS[band]||BAND_COLORS.Unknown;
  const bg = BAND_BG[band]||BAND_BG.Unknown;
  return <span className="band-chip" style={{background:bg, color:c, border:`1px solid ${c}33`}}>{band||'Unknown'}</span>;
}

function RatingBar({ label, raw }) {
  const text = RATING_MAP[raw]; const score = RATING_SCORES[raw]; if (!text) return null;
  return (
    <div className="rating-row">
      <div className="rating-label">{label}</div>
      <div className="rating-bar-wrap"><div className="rating-bar-fill" style={{ width:`${score}%`, background:BAND_COLORS[text] }} /></div>
      <div className="rating-chip" style={{ color:BAND_COLORS[text] }}>{text}</div>
    </div>
  );
}

function SchoolDetail({ school, onClose }) {
  if (!school) return null;
  const band = school.score_band || school.quality_label || 'Unknown';
  const website = school.website ? (school.website.startsWith('http') ? school.website : `https://${school.website}`) : null;
  return (
    <div className="detail-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="detail-panel">
        <div className="detail-header">
          <button className="detail-close" onClick={onClose}>✕</button>
          <div className="detail-phase-tag">{school.phase} · {school.school_type}</div>
          <div className="detail-name">{school.name}</div>
          <div className="detail-la">📍 {school.local_authority} · {school.postcode}</div>
          <div className="detail-score-row">
            <div className="detail-score-box"><div className="detail-score-val">{school.ofsted_score??'—'}</div><div className="detail-score-desc">Score</div></div>
            <div className="detail-score-box" style={{flex:1.6}}><div style={{paddingTop:4}}><BandChip band={band} /></div><div className="detail-score-desc" style={{marginTop:5}}>Rating</div></div>
            <div className="detail-score-box"><div className="detail-score-val">{school.pupils??'—'}</div><div className="detail-score-desc">Pupils</div></div>
          </div>
        </div>
        <div className="detail-body">
          <div className="detail-section">
            <div className="detail-section-title">Ofsted Ratings</div>
            <RatingBar label="Quality of education" raw={school.quality_raw} />
            <RatingBar label="Behaviour & attitudes" raw={school.behaviour_raw} />
            <RatingBar label="Personal development" raw={school.personal_dev_raw} />
            <RatingBar label="Leadership & management" raw={school.leadership_raw} />
          </div>
          <div className="detail-section">
            <div className="detail-section-title">School Information</div>
            <div className="detail-grid">
              <div className="detail-field"><span className="detail-field-label">Age Range</span><span className="detail-field-val">{school.age_from}–{school.age_to}</span></div>
              <div className="detail-field"><span className="detail-field-label">Gender</span><span className="detail-field-val">{school.gender||'—'}</span></div>
              <div className="detail-field"><span className="detail-field-label">Sixth Form</span><span className="detail-field-val">{school.sixth_form==='Has a sixth form'?'✓ Yes':'No'}</span></div>
              <div className="detail-field"><span className="detail-field-label">Admissions</span><span className="detail-field-val">{school.admissions||'—'}</span></div>
              <div className="detail-field"><span className="detail-field-label">Safeguarding</span><span className="detail-field-val" style={{color:school.safeguarding==='Yes'?'#059669':'#DC2626'}}>{school.safeguarding==='Yes'?'✓ Effective':school.safeguarding||'—'}</span></div>
              <div className="detail-field"><span className="detail-field-label">Last Inspection</span><span className="detail-field-val">{school.inspection_date||'—'}</span></div>
              {school.pct_fsm!=null&&<div className="detail-field"><span className="detail-field-label">Free School Meals</span><span className="detail-field-val">{school.pct_fsm}%</span></div>}
              {school.idaci_quintile!=null&&<div className="detail-field"><span className="detail-field-label">IDACI Quintile</span><span className="detail-field-val">Quintile {school.idaci_quintile}</span></div>}
              {school.head_name&&<div className="detail-field" style={{gridColumn:'span 2'}}><span className="detail-field-label">Headteacher</span><span className="detail-field-val">{school.head_name}</span></div>}
              {school.telephone&&<div className="detail-field"><span className="detail-field-label">Telephone</span><span className="detail-field-val">{school.telephone}</span></div>}
              {school.mat_name&&<div className="detail-field" style={{gridColumn:'span 2'}}><span className="detail-field-label">Academy Trust</span><span className="detail-field-val">{school.mat_name}</span></div>}
              {school.religious_character&&school.religious_character!=='Does not apply'&&<div className="detail-field" style={{gridColumn:'span 2'}}><span className="detail-field-label">Religious Character</span><span className="detail-field-val">{school.religious_character}</span></div>}
            </div>
          </div>
          <div style={{display:'flex',gap:9}}>
            {website&&<a href={website} target="_blank" rel="noopener noreferrer" style={{flex:1,display:'block',textAlign:'center',padding:'10px',background:'var(--bg)',color:'var(--ink)',borderRadius:8,fontWeight:600,fontSize:'0.82rem',textDecoration:'none',border:'1.5px solid var(--border)'}}>School website →</a>}
            {school.ofsted_url&&<a href={school.ofsted_url} target="_blank" rel="noopener noreferrer" style={{flex:1,display:'block',textAlign:'center',padding:'10px',background:'var(--ink)',color:'var(--gold)',borderRadius:8,fontWeight:600,fontSize:'0.82rem',textDecoration:'none'}}>Ofsted report →</a>}
          </div>
        </div>
      </div>
    </div>
  );
}

function MapView({ schools, onSelect }) {
  const mapInstance = useRef(null);
  const markersRef = useRef([]);
  useEffect(() => {
    if (mapInstance.current) return;
    mapInstance.current = L.map('school-map').setView([51.505, -0.1], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap', maxZoom: 18 }).addTo(mapInstance.current);
  }, []);
  useEffect(() => {
    if (!mapInstance.current) return;
    markersRef.current.forEach(m => m.remove()); markersRef.current = [];
    schools.filter(s => s.lat && s.lng).forEach(school => {
      const band = school.score_band || school.quality_label || 'Unknown';
      const color = BAND_COLORS[band] || '#9CA3AF';
      const icon = L.divIcon({ className: '', html: `<div style="width:11px;height:11px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.25)"></div>`, iconSize:[11,11], iconAnchor:[5,5] });
      const m = L.marker([school.lat, school.lng], { icon }).addTo(mapInstance.current);
      m.bindPopup(`<div style="font-family:Inter,sans-serif;min-width:180px"><div style="font-family:'Playfair Display',serif;font-weight:700;font-size:0.92rem;margin-bottom:2px">${school.name}</div><div style="font-size:0.73rem;color:#6B7280;margin-bottom:7px">${school.local_authority} · ${school.postcode}</div><span style="background:${BAND_BG[band]||'#F9FAFB'};color:${color};border:1px solid ${color}33;display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.67rem;font-weight:600">${band}</span><br/><button onclick="window.__sel(${school.urn})" style="display:block;width:100%;text-align:center;padding:7px;background:#111827;color:#D4A843;border-radius:7px;font-size:0.75rem;font-weight:600;cursor:pointer;border:none;font-family:Inter,sans-serif;margin-top:8px">View details →</button></div>`);
      markersRef.current.push(m);
    });
    window.__sel = urn => { const s = schools.find(x => x.urn === urn); if (s) onSelect(s); };
  }, [schools]);
  const withCoords = schools.filter(s => s.lat && s.lng).length;
  return (
    <div>
      <div className="map-wrap"><div id="school-map" /></div>
      <div className="map-legend">
        {Object.entries(BAND_COLORS).filter(([b]) => b !== 'Unknown').map(([band, color]) => (
          <span key={band}><span className="map-legend-dot" style={{background:color}} />{band}</span>
        ))}
        <span style={{marginLeft:'auto'}}>{withCoords} of {schools.length} mapped</span>
      </div>
    </div>
  );
}

function StatsPage({ schools }) {
  const byBand = useMemo(() => { const c={}; schools.forEach(s=>{const b=s.score_band||s.quality_label||'Unknown';c[b]=(c[b]||0)+1;}); return c; }, [schools]);
  const byPhase = useMemo(() => { const c={}; schools.forEach(s=>{c[s.phase||'Unknown']=(c[s.phase||'Unknown']||0)+1;}); return Object.entries(c).sort((a,b)=>b[1]-a[1]); }, [schools]);
  const byLA = useMemo(() => { const c={}; schools.forEach(s=>{c[s.local_authority||'Unknown']=(c[s.local_authority||'Unknown']||0)+1;}); return Object.entries(c).sort((a,b)=>b[1]-a[1]).slice(0,16); }, [schools]);
  const rated = schools.filter(s=>s.ofsted_score!=null);
  const avg = rated.length ? Math.round(rated.reduce((a,s)=>a+s.ofsted_score,0)/rated.length) : 0;
  return (
    <div>
      <div className="stats-grid">
        {[{num:schools.length,label:'Total Schools'},{num:byBand['Outstanding']||0,label:'Outstanding'},{num:byBand['Good']||0,label:'Good'},{num:avg,label:'Avg Score'}].map(({num,label})=>(
          <div key={label} className="stat-card"><div className="stat-card-num">{num}</div><div className="stat-card-label">{label}</div></div>
        ))}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14,marginBottom:14}}>
        <div className="chart-section">
          <div className="chart-title">By Ofsted rating</div>
          {['Outstanding','Good','Requires improvement','Inadequate','Unknown'].map(band => { const count=byBand[band]||0; if(!count) return null; const pct=Math.round((count/schools.length)*100); return (<div key={band} className="bar-chart-row"><div className="bar-chart-label">{band}</div><div className="bar-chart-wrap"><div className="bar-chart-fill" style={{width:`${pct}%`,background:BAND_COLORS[band]}}>{pct>6?`${pct}%`:''}</div></div><div className="bar-chart-count">{count}</div></div>); })}
        </div>
        <div className="chart-section">
          <div className="chart-title">By phase</div>
          {byPhase.map(([phase,count])=>{const pct=Math.round((count/byPhase[0][1])*100);return(<div key={phase} className="bar-chart-row"><div className="bar-chart-label">{phase}</div><div className="bar-chart-wrap"><div className="bar-chart-fill" style={{width:`${pct}%`,background:'#111827'}}>{count}</div></div><div className="bar-chart-count">{count}</div></div>);})}
        </div>
      </div>
      <div className="chart-section">
        <div className="chart-title">By London borough</div>
        {byLA.map(([la,count])=>{const pct=Math.round((count/byLA[0][1])*100);return(<div key={la} className="bar-chart-row"><div className="bar-chart-label">{la}</div><div className="bar-chart-wrap"><div className="bar-chart-fill" style={{width:`${pct}%`,background:'#D4A843'}}>{count}</div></div><div className="bar-chart-count">{count}</div></div>);})}
      </div>
    </div>
  );
}

function ScoreCard({ school, onClick }) {
  const band = school.score_band || school.quality_label || 'Unknown';
  const color = BAND_COLORS[band] || '#9CA3AF';
  const admissions = school.admissions;
  const showAdm = admissions && admissions !== 'Not applicable';
  return (
    <div className="school-card" style={{'--band-color': color}} onClick={() => onClick(school)}>
      <div className="card-top">
        <span className="card-phase">{school.phase}</span>
        {showAdm && <span className="pill" style={admissions==='Selective'?{background:'#FFFBEB',color:'#D97706',border:'1px solid #FDE68A'}:{background:'var(--bg)',color:'var(--ink-3)',border:'1px solid var(--border)'}}>{admissions==='Selective'?'🎓 Selective':admissions}</span>}
      </div>
      <div className="card-name">{school.name}</div>
      <div className="card-la">📍 {school.local_authority} · {school.postcode}</div>
      <div className="card-rating-bar">
        <div className="card-rating-track"><div className="card-rating-fill" style={{width:`${school.ofsted_score??0}%`, background:color}} /></div>
        <span className="card-rating-label" style={{color}}>{band}</span>
      </div>
      <div className="card-pills">
        {school.sixth_form==='Has a sixth form'&&<span className="pill" style={{background:'#F5F3FF',color:'#7C3AED',border:'1px solid #DDD6FE'}}>Sixth form</span>}
        {school.gender&&school.gender!=='Mixed'&&<span className="pill" style={{background:'#FDF2F8',color:'#9D174D',border:'1px solid #FBCFE8'}}>{school.gender}</span>}
        {school.religious_character&&school.religious_character!=='Does not apply'&&school.religious_character!=='None'&&<span className="pill" style={{background:'var(--green-lt)',color:'var(--green)',border:'1px solid #A7F3D0'}}>⛪ {school.religious_character}</span>}
      </div>
      <div className="card-meta">
        <span>👥 {school.pupils??'—'} pupils</span>
        {school.inspection_date&&<span>📅 {school.inspection_date}</span>}
        {school.imd_score!=null&&<span>IMD {school.imd_score}</span>}
      </div>
    </div>
  );
}

// ── Property View ─────────────────────────────────────────────────────────────

const OFSTED_CHIPS = [
  { label:'Outstanding', color:'#059669' },
  { label:'Good',        color:'#2563EB' },
  { label:'Requires improvement', color:'#D97706' },
];

function PropertyView({ schools }) {
  const [postcode, setPostcode]       = useState('');
  const [selSchool, setSelSchool]     = useState('');
  const [radius, setRadius]           = useState('0.5');
  const [tenure, setTenure]           = useState('sale');
  const [bedsMin, setBedsMin]         = useState('2');
  const [ofstedF, setOfstedF]         = useState(new Set(['Outstanding','Good']));
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState(null);
  const [results, setResults]         = useState(null);
  const [saved, setSaved]             = useState(new Set());

  const schoolOptions = useMemo(() => schools.filter(s=>s.postcode).sort((a,b)=>a.name.localeCompare(b.name)), [schools]);

  function toggleOfsted(label) {
    setOfstedF(prev => { const n=new Set(prev); n.has(label)?n.delete(label):n.add(label); return n; });
  }

  function ofstedMin() {
    if (ofstedF.has('Requires improvement')) return 3;
    if (ofstedF.has('Good')) return 2;
    return 1;
  }

  async function doSearch() {
    const pc = selSchool || postcode.trim();
    if (!pc) { setError('Enter a postcode or pick a school.'); return; }
    setError(null); setLoading(true); setResults(null);
    try {
      const p = new URLSearchParams({ postcode:pc, radius, tenure, beds_min:bedsMin, ofsted_min:ofstedMin() });
      const res = await fetch(`${PROP_API}/search?${p}`);
      if (!res.ok) { const e=await res.json(); throw new Error(e.error||'Search failed'); }
      setResults(await res.json());
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const filtered = useMemo(() => {
    if (!results) return [];
    return results.properties.filter(p => {
      if (!p.nearbySchools?.length) return true;
      return p.nearbySchools.some(s => ofstedF.has(s.ratingLabel));
    });
  }, [results, ofstedF]);

  return (
    <div className="pv-layout">
      {/* Sidebar filters */}
      <aside className="pv-sidebar">
        <div className="pv-sidebar-title">Find a home nearby</div>
        <div className="pv-sidebar-sub">Search by postcode or choose a school to find family properties within walking distance.</div>

        {schoolOptions.length > 0 && (
          <div className="pv-field">
            <div className="pv-field-label">Near a school</div>
            <select className="pv-select" value={selSchool} onChange={e => { setSelSchool(e.target.value); if(e.target.value) setPostcode(''); }}>
              <option value="">— choose a school —</option>
              {schoolOptions.map(s=><option key={s.urn} value={s.postcode}>{s.name}</option>)}
            </select>
          </div>
        )}

        <div className="pv-field">
          <div className="pv-field-label">Or enter a postcode</div>
          <input className="pv-input" type="text" placeholder="e.g. N1, SE22, EC1A 1BB" value={postcode} disabled={!!selSchool} onChange={e=>setPostcode(e.target.value)} onKeyDown={e=>e.key==='Enter'&&doSearch()} />
        </div>

        <div className="pv-field">
          <div className="pv-field-label">Radius</div>
          <select className="pv-select" value={radius} onChange={e=>setRadius(e.target.value)}>
            <option value="0.25">¼ mile</option>
            <option value="0.5">½ mile</option>
            <option value="1">1 mile</option>
            <option value="2">2 miles</option>
          </select>
        </div>

        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:14}}>
          <div className="pv-field" style={{marginBottom:0}}>
            <div className="pv-field-label">Type</div>
            <select className="pv-select" value={tenure} onChange={e=>setTenure(e.target.value)}>
              <option value="sale">For sale</option>
              <option value="rent">To rent</option>
            </select>
          </div>
          <div className="pv-field" style={{marginBottom:0}}>
            <div className="pv-field-label">Bedrooms</div>
            <select className="pv-select" value={bedsMin} onChange={e=>setBedsMin(e.target.value)}>
              <option value="2">2+</option>
              <option value="3">3+</option>
              <option value="4">4+</option>
            </select>
          </div>
        </div>

        <div className="pv-divider" />
        <div className="pv-section-label">Ofsted rating nearby</div>
        <div className="pv-chips">
          {OFSTED_CHIPS.map(({label,color}) => (
            <div key={label} className={`pv-chip${ofstedF.has(label)?' on':''}`} onClick={()=>toggleOfsted(label)}>
              <span className="pv-chip-dot" style={{background:color}} />
              <span className="pv-chip-text">{label}</span>
              <span className="pv-chip-check">✓</span>
            </div>
          ))}
        </div>

        <button className="pv-search-btn" onClick={doSearch} disabled={loading}>
          {loading ? 'Searching…' : 'Find properties →'}
        </button>

        {selSchool && <button className="clear-btn" style={{width:'100%',marginTop:8,textAlign:'center'}} onClick={()=>setSelSchool('')}>✕ Clear school</button>}
      </aside>

      {/* Main results area */}
      <div className="pv-main">
        {/* Hero banner — only when no results */}
        {!results && !loading && (
          <div className="pv-hero">
            <div className="pv-hero-tag">New feature</div>
            <div className="pv-hero-title">Properties matched to school catchments</div>
            <div className="pv-hero-sub">Every listing shows the nearest Ofsted-rated schools and their walking distance — so you can find the right home and the right school at the same time.</div>
          </div>
        )}

        {loading && <div className="pv-status"><div className="pv-spinner"/>Searching Zoopla listings and Ofsted data…</div>}
        {error && <div className="pv-error">⚠ {error}</div>}

        {results?.schools?.length > 0 && (
          <div className="pv-schools-found">
            <div className="pv-sf-label">Schools found nearby · {results.meta.schoolsFound}</div>
            <div className="pv-sf-list">
              {results.schools.slice(0,7).map(s=>(
                <span key={s.urn||s.name} className="pv-sf-badge">
                  <span className="pv-sf-dot" style={{background:BAND_COLORS[s.ratingLabel]||'#9CA3AF'}} />
                  {s.name}
                </span>
              ))}
            </div>
          </div>
        )}

        {results && (
          <>
            <div className="pv-status">{filtered.length} propert{filtered.length===1?'y':'ies'} found{results.meta?.schoolsFound ? ` · ${results.meta.schoolsFound} schools nearby` : ''}</div>
            <div className="pv-grid">
              {filtered.length===0
                ? <div className="pv-empty"><div className="pv-empty-icon">🏘</div><h3>No matches</h3><p>Try a wider radius or adjusting the Ofsted filter.</p></div>
                : filtered.map(p=>(
                  <div key={p.id} className="pv-card">
                    <div className="pv-card-thumb" style={{position:'relative'}}>
                      {p.thumbnail ? <img src={p.thumbnail} alt={p.address} loading="lazy"/> : '🏡'}
                      <span className="pv-card-tenure">{p.tenure==='rent'?'To rent':'For sale'}</span>
                      <button className={`pv-card-save${saved.has(p.id)?' saved':''}`} onClick={()=>setSaved(prev=>{const n=new Set(prev);n.has(p.id)?n.delete(p.id):n.add(p.id);return n;})}>
                        {saved.has(p.id)?'★':'☆'}
                      </button>
                    </div>
                    <div className="pv-card-body">
                      <div className="pv-price">{p.price}</div>
                      <div className="pv-address">{p.address}</div>
                      <div className="pv-pills">
                        <span className="pv-pill">{p.beds} bed</span>
                        {p.baths>0&&<span className="pv-pill">{p.baths} bath</span>}
                        <span className="pv-pill">{p.type||'Property'}</span>
                      </div>
                      {(p.nearbySchools||[]).slice(0,2).length>0&&(
                        <div className="pv-schools">
                          {(p.nearbySchools||[]).slice(0,2).map(s=>(
                            <div key={s.urn||s.name} className="pv-school-row">
                              <span className="pv-s-dot" style={{background:BAND_COLORS[s.ratingLabel]||'#9CA3AF'}} />
                              <div><div className="pv-s-name">{s.name}</div><div className="pv-s-detail">{s.ratingLabel}{s.walkDistance&&s.walkDistance!=='N/A'?` · ${s.walkDistance} walk`:''}</div></div>
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="pv-cta">
                        <button className="pv-btn-ghost" onClick={()=>p.url&&window.open(p.url,'_blank')}>View listing</button>
                        <button className="pv-btn-solid" onClick={()=>setSaved(prev=>{const n=new Set(prev);n.has(p.id)?n.delete(p.id):n.add(p.id);return n;})}>{saved.has(p.id)?'✓ Saved':'Save'}</button>
                      </div>
                    </div>
                  </div>
                ))
              }
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const [view, setView]           = useState('schools');
  const [displayMode, setDisplayMode] = useState('grid');
  const [schools, setSchools]     = useState([]);
  const [loading, setLoading]     = useState(true);
  const [selected, setSelected]   = useState(null);
  const [page, setPage]           = useState(1);
  const PAGE_SIZE = 24;
  const [filters, setFilters]     = useState({ q:'', phase:'', local_authority:'', score_band:'' });

  useEffect(() => {
    async function load() {
      try { const r=await fetch(`${API_BASE}/schools?limit=500`); if(!r.ok) throw new Error(); const d=await r.json(); setSchools(d.schools); setLoading(false); return; } catch {}
      try { const r=await fetch(JSON_FALLBACK); if(!r.ok) throw new Error(); const d=await r.json(); setSchools(d); } catch { console.warn('Place schools.json alongside this file.'); }
      setLoading(false);
    }
    load();
  }, []);

  const phases = useMemo(() => [...new Set(schools.map(s=>s.phase).filter(Boolean))].sort(), [schools]);
  const localAuthorities = useMemo(() => [...new Set(schools.map(s=>s.local_authority).filter(Boolean))].sort(), [schools]);
  const filtered = useMemo(() => {
    let r = schools;
    if (filters.q) r=r.filter(s=>s.name.toLowerCase().includes(filters.q.toLowerCase())||(s.postcode||'').toLowerCase().includes(filters.q.toLowerCase()));
    if (filters.phase) r=r.filter(s=>s.phase===filters.phase);
    if (filters.local_authority) r=r.filter(s=>s.local_authority===filters.local_authority);
    if (filters.score_band) r=r.filter(s=>(s.score_band||s.quality_label)===filters.score_band);
    return r.sort((a,b)=>(b.ofsted_score??-1)-(a.ofsted_score??-1));
  }, [schools, filters]);

  const totalPages = Math.ceil(filtered.length/PAGE_SIZE);
  const paged = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  const setFilter = useCallback((k,v)=>{setFilters(f=>({...f,[k]:v}));setPage(1);},[]);
  const clearFilters = ()=>{setFilters({q:'',phase:'',local_authority:'',score_band:''});setPage(1);};
  const hasFilters = filters.q||filters.phase||filters.local_authority||filters.score_band;
  const stats = useMemo(()=>{const rated=schools.filter(s=>s.ofsted_score!=null);return{total:schools.length,outstanding:schools.filter(s=>(s.score_band||s.quality_label)==='Outstanding').length,avg:rated.length?Math.round(rated.reduce((a,s)=>a+s.ofsted_score,0)/rated.length):0};},[schools]);

  const NAV = [
    { id:'schools', icon:'▤', label:'Schools' },
    { id:'map',     icon:'◎', label:'Map' },
    { id:'stats',   icon:'▦', label:'Statistics' },
    { id:'property',icon:'⌂', label:'Properties' },
  ];

  return (
    <>
      <nav className="topbar">
        <div className="topbar-logo">
          <div className="topbar-logo-mark">LS</div>
          <span className="topbar-logo-text">London <span>Schools</span></span>
        </div>
        <div className="topbar-nav">
          {NAV.map(n=>(
            <button key={n.id} className={`topbar-nav-btn${view===n.id?' active':''}`} onClick={()=>setView(n.id)}>
              <span style={{fontSize:'0.95rem'}}>{n.icon}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </div>
      </nav>

      <div className="hero">
        <div className="hero-inner">
          <div>
            <div className="hero-eyebrow">Ofsted data · 32 London boroughs</div>
            <h1>Find the right school<br />in <em>London</em></h1>
            <p className="hero-sub">Compare schools using official Ofsted data, deprivation indices, and composite scoring. Now with nearby property search.</p>
          </div>
          <div className="hero-stats">
            {[{n:stats.total,l:'Schools'},{n:stats.outstanding,l:'Outstanding'},{n:stats.avg,l:'Avg score'},{n:32,l:'Boroughs'}].map(({n,l})=>(
              <div key={l} className="hero-stat"><div className="hero-stat-num">{n}</div><div className="hero-stat-label">{l}</div></div>
            ))}
          </div>
        </div>
      </div>

      <div className="main">
        {loading ? (
          <div className="loading"><div className="spinner"/>Loading schools…</div>
        ) : view==='property' ? (
          <PropertyView schools={schools} />
        ) : view==='stats' ? (
          <StatsPage schools={schools} />
        ) : view==='map' ? (
          <>
            <div className="filter-bar">
              <div className="fsearch" style={{flex:1,minWidth:200}}><span className="fsearch-icon">🔍</span><input type="text" placeholder="Filter by name or postcode…" value={filters.q} onChange={e=>setFilter('q',e.target.value)}/></div>
              <div className="fgroup"><span className="flabel">Phase</span><select value={filters.phase} onChange={e=>setFilter('phase',e.target.value)}><option value="">All phases</option>{phases.map(p=><option key={p} value={p}>{p}</option>)}</select></div>
              <div className="fgroup"><span className="flabel">Borough</span><select value={filters.local_authority} onChange={e=>setFilter('local_authority',e.target.value)}><option value="">All boroughs</option>{localAuthorities.map(la=><option key={la} value={la}>{la}</option>)}</select></div>
              <div className="fgroup"><span className="flabel">Rating</span><select value={filters.score_band} onChange={e=>setFilter('score_band',e.target.value)}><option value="">All ratings</option>{['Outstanding','Good','Requires improvement','Inadequate'].map(b=><option key={b} value={b}>{b}</option>)}</select></div>
              {hasFilters&&<button className="clear-btn" onClick={clearFilters}>✕ Clear</button>}
            </div>
            <MapView schools={filtered} onSelect={setSelected}/>
          </>
        ) : (
          <>
            <div className="filter-bar">
              <div className="fsearch"><span className="fsearch-icon">🔍</span><input type="text" placeholder="Search by name or postcode…" value={filters.q} onChange={e=>setFilter('q',e.target.value)}/></div>
              <div className="fgroup"><span className="flabel">Phase</span><select value={filters.phase} onChange={e=>setFilter('phase',e.target.value)}><option value="">All phases</option>{phases.map(p=><option key={p} value={p}>{p}</option>)}</select></div>
              <div className="fgroup"><span className="flabel">Borough</span><select value={filters.local_authority} onChange={e=>setFilter('local_authority',e.target.value)}><option value="">All boroughs</option>{localAuthorities.map(la=><option key={la} value={la}>{la}</option>)}</select></div>
              <div className="fgroup"><span className="flabel">Rating</span><select value={filters.score_band} onChange={e=>setFilter('score_band',e.target.value)}><option value="">All ratings</option>{['Outstanding','Good','Requires improvement','Inadequate'].map(b=><option key={b} value={b}>{b}</option>)}</select></div>
              {hasFilters&&<button className="clear-btn" onClick={clearFilters}>✕ Clear</button>}
            </div>
            <div className="results-header">
              <div className="results-count">Showing <strong>{filtered.length}</strong> school{filtered.length!==1?'s':''}{schools.length!==filtered.length?` of ${schools.length}`:''}</div>
              <div className="view-toggle">
                <button className={`view-btn${displayMode==='grid'?' active':''}`} onClick={()=>setDisplayMode('grid')}>⊞</button>
                <button className={`view-btn${displayMode==='table'?' active':''}`} onClick={()=>setDisplayMode('table')}>☰</button>
              </div>
            </div>
            {filtered.length===0 ? (
              <div className="empty-state"><h3>No schools found</h3><p>Try adjusting your filters.</p></div>
            ) : displayMode==='grid' ? (
              <div className="school-grid">{paged.map(s=><ScoreCard key={s.urn} school={s} onClick={setSelected}/>)}</div>
            ) : (
              <table className="school-table">
                <thead><tr><th>#</th><th>School</th><th>Borough</th><th>Phase</th><th>Ofsted grade</th><th>Admissions</th><th>Pupils</th><th>Inspected</th></tr></thead>
                <tbody>
                  {paged.map((s,i)=>{const band=s.score_band||s.quality_label||'Unknown';const adm=s.admissions;return(
                    <tr key={s.urn} onClick={()=>setSelected(s)}>
                      <td><span className="rank-num">{(page-1)*PAGE_SIZE+i+1}</span></td>
                      <td style={{fontWeight:600,maxWidth:260}}>{s.name}</td>
                      <td style={{color:'var(--ink-3)'}}>{s.local_authority}</td>
                      <td style={{color:'var(--ink-3)',fontSize:'0.78rem'}}>{s.phase}</td>
                      <td><BandChip band={band}/></td>
                      <td style={{fontSize:'0.8rem'}}>{adm==='Selective'?<span style={{color:'#D97706',fontWeight:600}}>🎓 Selective</span>:adm==='Non-selective'?<span style={{color:'var(--ink-3)'}}>Non-selective</span>:<span style={{color:'#D1D5DB'}}>—</span>}</td>
                      <td style={{color:'var(--ink-3)'}}>{s.pupils??'—'}</td>
                      <td style={{color:'var(--ink-3)',fontSize:'0.78rem'}}>{s.inspection_date||'—'}</td>
                    </tr>
                  );})}
                </tbody>
              </table>
            )}
            {totalPages>1&&(
              <div className="pagination">
                <button className="page-btn" onClick={()=>setPage(p=>p-1)} disabled={page===1}>‹</button>
                {Array.from({length:Math.min(7,totalPages)},(_,i)=>{let p;if(totalPages<=7)p=i+1;else if(page<=4)p=i+1;else if(page>=totalPages-3)p=totalPages-6+i;else p=page-3+i;return<button key={p} className={`page-btn${page===p?' active':''}`} onClick={()=>setPage(p)}>{p}</button>;})  }
                <button className="page-btn" onClick={()=>setPage(p=>p+1)} disabled={page===totalPages}>›</button>
              </div>
            )}
          </>
        )}
      </div>
      {selected&&<SchoolDetail school={selected} onClose={()=>setSelected(null)}/>}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>
