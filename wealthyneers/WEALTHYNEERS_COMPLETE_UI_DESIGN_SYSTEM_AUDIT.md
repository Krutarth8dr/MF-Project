# WEALTHYNEERS — COMPLETE WEBSITE UI, DESIGN SYSTEM & RESPONSIVE ARCHITECTURE AUDIT

**Document Type:** Technical & Visual Architecture Handoff  
**Target Audience:** Lead AI Engineers, Technical Architects, Frontend Developers  
**Application:** Wealthyneers Institutional Mutual Fund Research Platform  
**Root Path:** `D:\MF Project\wealthyneers`  
**Primary Styling File:** `src/app/globals.css` (8,095 lines)  
**Framework:** Next.js 16.2.6 (App Router), React 19.2.4, Recharts 3.8.1, Supabase Client 2.105.4  
**Audit Mode:** STRICTLY READ-ONLY (No code, database, or configuration altered)  

---

## 1. EXECUTIVE OVERVIEW

Wealthyneers is an institutional-grade financial data intelligence and visualization platform tracking portfolio holdings across 25 Asset Management Companies (AMCs) and 391 mutual fund schemes in India. The application serves retail investors and high-net-worth market participants who analyze statutory portfolio disclosures to uncover domestic institutional accumulation, distribution, turning points, and consensus direction.

### Visual Identity Summary
The user interface is characterized by a high-density, analytical fintech visual language:
- **Clean, high-contrast typography** optimized for scanning dense numerical quantities, ISIN codes, and security names.
- **Deep oceanic teal branding** (`#0a4d68`) paired with vibrant cyan digital accents (`#05bfdb`) evoking institutional credibility and modern financial analytics.
- **Strictly card-based layouts** with subtle borders (`#e9ecef`), delicate elevations (`rgba(0,0,0,0.03)` to `rgba(0,0,0,0.08)`), and rounded corners (`0.5rem` to `1.25rem`).
- **Semantic directional cues**: Universal financial signals (Green for accumulation/buying, Red for distribution/selling, Gray/Slate for neutral/unchanged, Amber for alerts and highlights).
- **Three-tier responsive architecture**: Distinct desktop, tablet, and mobile presentation modes engineered using layered media query breakpoints, responsive Recharts containers, sticky horizontal table scrolling, and a dedicated mobile navigation drawer.

---

## 2. TECHNOLOGY & STYLING ARCHITECTURE

### 2.1 Styling Paradigm
Wealthyneers employs a **Centralized Global CSS Architecture**. Instead of CSS Modules, Tailwind CSS, or CSS-in-JS runtimes, the entire visual layer is declared inside:
- [`src/app/globals.css`](file:///d:/MF%20Project/wealthyneers/src/app/globals.css) (8,095 lines, ~165 KB)

The root layout imports this single stylesheet:
```javascript
// src/app/layout.js:1
import "./globals.css";
```

### 2.2 Component & Layout Architecture
- **Root Layout (`src/app/layout.js`):**
  - Injects global HTML structure, Razorpay checkout script, sticky `<header className="header">` containing `<AuthNav />`, sticky secondary sub-navigation `<ReportsNav />`, the route's `{children}`, and the global `<footer className="site-footer">`.
- **Client Components (`'use client'`):**
  - All interactive reports (`/report1` through `/report6`), auth forms, dashboard, profile, and navigation components are React client components using hooks (`useState`, `useEffect`, `useCallback`, `useMemo`, `useRef`).
- **Data Visualizations:**
  - Powered by **Recharts (`recharts: ^3.8.1`)** wrapped in `<ResponsiveContainer width="100%">` elements.
- **Database & Auth:**
  - Direct client-side calls to Supabase RPCs and tables (`@supabase/supabase-js: ^2.105.4`), using session caching helpers (`src/lib/subscriptionCache.js`).

### 2.3 Style Isolation & Namespacing
To avoid cross-page leakage while maintaining a single global stylesheet, the codebase uses a **strict class-prefix namespacing convention**:
- Global primitives: `.btn`, `.container`, `.header`, `.nav-links`, `.footer`
- Secondary sub-nav: `.global-reports-nav`, `.global-nav-tab`
- Mobile drawer: `.mobile-nav-toggle`, `.mobile-nav-drawer`, `.mobile-nav-overlay`
- Landing page: `.hero`, `.reports`, `.report-card`, `.pricing-card`, `.cov-*`
- Dashboard Hub: `.dash-page`, `.dash-subnav`, `.dash-report-tile`, `.dash-content`
- Report 1: `.r1-page`, `.r1-header`, `.r1-filter-bar`, `.r1-chart-card`, `.r1-tooltip`
- Report 2: `.r2-page`, `.r2-header`, `.r2-filter-bar`, `.r2-table`, `.r2-stat-card`
- Report 3: `.r3-page`, `.r3-header`, `.r3-chart-card`, `.r3-sec-dropdown`, `.r3-amc-legend`
- Report 4: `.r4-page`, `.r4-header`, `.r4-matrix-table`, `.r4-dir-badge`
- Report 5: `.r5-page`, `.r5-header`, `.r5-ranking-table`, `.r5-score-pill`
- Report 6: `.r6-page`, `.r6-header`, `.r6-table`, `.r6-consensus-badge`
- Profile / Account: `.profile-page`, `.profile-hero`, `.profile-grid`, `.profile-card`
- Questionnaire: `.questionnaire-form`, `.q-section-card`, `.q-opt-btn`, `.q-field`
- Guide Modal: `.guide-modal-overlay`, `.guide-modal-container`, `.guide-tab-btn`
- Legal & Content: `.legal-page`, `.legal-card`, `.legal-section`, `.contact-grid`

---

## 3. DESIGN TOKENS & COLOR PALETTE

### 3.1 CSS Custom Properties (`globals.css:1-21`)

#### Light Mode Tokens (Default Active Theme)
```css
:root {
  --primary: #0a4d68;     /* Deep Oceanic Teal / Navy (Brand Core) */
  --secondary: #5a6b7c;   /* Slate Gray / Muted Metal (Secondary Text) */
  --accent: #05bfdb;      /* Electric Cyan / Bright Aqua (Interactive Highlights) */
  --background: #f8f9fa;  /* Ultra-light Neutral Gray (Canvas Background) */
  --foreground: #212529;  /* Off-black / Charcoal (Primary Body & Headings) */
  --card-bg: #ffffff;     /* Pure White (Card, Modal & Panel Surfaces) */
  --border: #e9ecef;      /* Soft Hairline Gray (Card & Divider Borders) */
}
```

#### Dark Mode Tokens (`globals.css:11-21`)
Declared via media query `@media (prefers-color-scheme: dark)`. Note that most report components provide inline explicit fallbacks or enforce light backgrounds for analytical data density:
```css
@media (prefers-color-scheme: dark) {
  :root {
    --primary: #05bfdb;
    --secondary: #a0aec0;
    --accent: #00ffca;
    --background: #121212;
    --foreground: #f8f9fa;
    --card-bg: #1e1e1e;
    --border: #2d2d2d;
  }
}
```

### 3.2 Semantic & Directional Palette

| Semantic Role | Hex Value | RGB / RGBA | Usage Location |
| :--- | :--- | :--- | :--- |
| **Brand Primary** | `#0a4d68` | `rgb(10, 77, 104)` | Buttons, active tabs, header logo, line chart strokes, title accents |
| **Brand Primary Hover** | `#083c52` | `rgb(8, 60, 82)` | Primary button hover state (`.btn-primary:hover`) |
| **Brand Accent** | `#05bfdb` | `rgb(5, 191, 219)` | Active chart dot fill, highlights, coverage badges, focus outlines |
| **Secondary Accent** | `#0284c7` | `rgb(2, 132, 199)` | Fund coverage highlights, links, secondary action pills |
| **Bullish / Buying / Positive** | `#059669` / `#16a34a` / `#198754` | `rgba(16, 185, 129, 0.12)` | Buying direction badges (`🟢`), Net Buy rankings, active subscription pill |
| **Bearish / Selling / Negative** | `#dc2626` / `#ef4444` / `#b02a37` | `rgba(239, 68, 68, 0.12)` | Selling direction badges (`🔴`), Net Sell rankings, expired status pill, logout btn |
| **Neutral / Unchanged** | `#64748b` / `#6c757d` | `rgba(100, 116, 139, 0.12)` | Flat direction badges (`⚪`), unranked items, inactive badges |
| **Warning / Attention** | `#d97706` / `#f59e0b` | `rgba(245, 158, 11, 0.12)` | Pending subscriptions, Breadth Rankings live badge |
| **Institutional Gold / Warmth** | `#c39354` | `rgba(195, 147, 84, 0.15)` | DIY Invest badge text, historical disclaimer border |
| **Error / Alert Text** | `#ff6b6b` / `#dc2626` | `rgb(255, 107, 107)` | Locked report label, error messages, form error bars |

### 3.3 AMC Categorical Color Map (`src/app/report3/page.jsx:22-42`)
For multi-line institutional comparison charts (Report 3), AMCs are mapped to deterministic hex colors:
- **HDFC Mutual Fund:** `#0a4d68`
- **ICICI Prudential Mutual Fund:** `#d9381e`
- **SBI MF:** `#198754`
- **Nippon India Mutual Fund:** `#e67e22`
- **Kotak MF:** `#6f42c1`
- **AXIS:** `#b02a37`
- **QUANT:** `#05bfdb`
- **PPFAS Mutual Fund:** `#20c997`
- **DSP Mutual Fund:** `#0dcaf0`
- **ABSL:** `#fd7e14`
- **JIO_BLACKROCK:** `#212529`
- **Bank Of India:** `#6610f2`
- **Invesco Mutual Fund:** `#084298`
- *Fallback Cycle Palette:* `['#0a4d68', '#05bfdb', '#d9381e', '#198754', '#e67e22', '#6f42c1', '#20c997', '#b02a37', '#0dcaf0', '#fd7e14', '#6610f2', '#084298', '#d63384', '#6c757d', '#3d5a80']`

---

## 4. TYPOGRAPHY SYSTEM

### 4.1 Font Family Stacks
- **Primary Body & UI Font (`globals.css:32`):**  
  `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- **Code / ISIN / Numerical Monospace Font (`globals.css:1835, 2021`):**  
  `'Courier New', monospace`

### 4.2 Hierarchy, Sizes & Line Heights

| Level | Desktop Size | Tablet (<= 900px / 768px) | Mobile (<= 480px) | Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Display Hero H1** | `3.5rem` (56px) | `2.25rem` (36px) | `1.85rem` (29.6px) | 700 / 800 | `1.2` – `1.25` | Home Hero headline |
| **Page Title H1** | `2.0rem` (32px) | `1.5rem` (24px) | `1.35rem` (21.6px) | 700 / 800 | `1.25` | Reports 1–6 titles, Dashboard H1 |
| **Section Title H2** | `2.5rem` (40px) | `1.75rem` (28px) | `1.45rem` (23.2px) | 700 / 800 | `1.3` | Landing sections, Invest H2 |
| **Card / Modal H2** | `1.35rem` – `1.4rem` | `1.2rem` | `1.1rem` | 700 / 800 | `1.3` | Guide Modal, Questionnaire Card |
| **Chart Title / Sub H3** | `1.1rem` – `1.25rem` | `1.05rem` | `1.0rem` | 700 | `1.35` | Chart Card Header, Report Card H3 |
| **Subtitle / Lead** | `0.95rem` (15.2px) | `0.92rem` | `0.88rem` | 400 / 500 | `1.6` | Subtitles below report titles |
| **Standard Body Text** | `0.95rem` – `1.0rem` | `0.92rem` | `0.9rem` | 400 | `1.6` – `1.65` | Paragraphs, descriptions, legal text |
| **Form Inputs & Selects**| `0.875rem` (14px) | `0.875rem` | `1.0rem` (16px) **(!)** | 400 / 500 | `1.4` | Desktop inputs: 14px; **<= 480px: 16px to prevent iOS auto-zoom** |
| **Table Cells & Chips** | `0.84rem` – `0.875rem` | `0.82rem` | `0.78rem` | 500 / 600 | `1.45` | Tabular data, security aliases |
| **Meta / Badges / Labels**| `0.72rem` – `0.78rem` | `0.72rem` | `0.70rem` | 600 / 700 | `1.2` – `1.3` | Tag pills, uppercase labels, tickers |

---

## 5. SPACING, CONTAINERS & LAYOUT SYSTEM

### 5.1 Container Widths
- **Universal Container (`.container`):** `max-width: 1200px; margin: 0 auto; padding: 0 2rem;`
  - Tablet (<= 1024px): `padding: 0 1.5rem;`
  - Mobile (<= 480px): `padding: 0 1rem;`
- **Report 1 Container (`.r1-page`):** `max-width: 1300px; margin: 0 auto; padding: 2rem 2rem 4rem;`
- **Report 2 Container (`.r2-page`):** `max-width: 1440px; margin: 0 auto; padding: 2rem 2rem 4rem;`
- **Report 3 Container (`.r3-page`):** `max-width: 100%; width: 100%; padding: 1.5rem 2.5rem 4rem;`
- **Report 4 Container (`.r4-page`):** `max-width: 1760px; width: 100%; padding: 1.5rem 2.5rem 4rem;`
- **Report 5 Container (`.r5-page`):** `max-width: 1440px; width: 100%; padding: 1.5rem 2rem 4rem;`
- **Report 6 Container (`.r6-page`):** `max-width: 1400px; margin: 0 auto; padding: 2rem 2rem 4rem;`
- **Dashboard Content (`.dash-content`):** `max-width: 1100px; margin: 0 auto; padding: 2.5rem 2rem 4rem;`
- **Profile Page (`.profile-page`):** `max-width: 1040px; margin: 2.5rem auto 4rem; padding: 0 1.5rem;`
- **Legal & Contact (`.legal-page`):** `max-width: 960px; margin: 0 auto; padding: 3rem 1.5rem 6rem;`
- **Auth Card (`.auth-card`):** `max-width: 400px; margin: 0 auto;`

### 5.2 Elevation & Shadow Tokens
- Hairline shadow: `0 1px 3px rgba(0, 0, 0, 0.03)`
- Card elevation: `0 2px 8px rgba(0, 0, 0, 0.04)`
- Interactive hover lift: `0 8px 24px rgba(10, 77, 104, 0.1)` (translates `translateY(-4px)`)
- Dropdown panel shadow: `0 8px 24px rgba(0, 0, 0, 0.1)`
- Modal overlay backdrop: `rgba(15, 23, 42, 0.72)` with `backdrop-filter: blur(6px)`
- Modal container shadow: `0 20px 50px rgba(0, 0, 0, 0.25)`

### 5.3 Border Radius Tokens
- Pills / Tickers: `9999px` or `2rem`
- Standard inputs & buttons: `0.5rem` (8px)
- Dropdown menus & chips: `0.6rem` (9.6px)
- Filter bars & Cards: `0.75rem` – `0.85rem` (12px – 13.6px)
- Large Feature / Pricing cards: `1.0rem` – `1.25rem` (16px – 20px)

---

## 6. UI COMPONENTS & INTERACTION STATES

### 6.1 Buttons
- **Primary Button (`.btn.btn-primary`):**  
  `background-color: var(--primary); color: white; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: 600;`  
  *Hover:* `background-color: #083c52; transform: translateY(-2px);`
- **Outline Button (`.btn.btn-outline`):**  
  `background-color: transparent; border: 2px solid var(--primary); color: var(--primary);`  
  *Hover:* `background-color: var(--primary); color: white;`
- **Report Description / How To Use Button (`.report-desc-btn`):**  
  `background-color: rgba(10, 77, 104, 0.08); color: var(--primary); border: 1px solid rgba(10, 77, 104, 0.22); border-radius: 9999px; font-size: 0.78rem; font-weight: 600;`  
  *Hover:* `background-color: var(--primary); color: #fff; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(10, 77, 104, 0.15);`
- **Disabled State (`button:disabled, .btn:disabled`):**  
  `opacity: 0.45; cursor: not-allowed; transform: none !important;`

### 6.2 Filter Controls & Inputs
- **Select Dropdowns (`.r1-select`):**  
  Custom chevron encoded SVG: `background-image: url("data:image/svg+xml,..."); appearance: none;`  
  *Focus:* `border-color: var(--primary); box-shadow: 0 0 0 3px rgba(10, 77, 104, 0.1); outline: none;`
- **Autocomplete Input (`.r1-search-input`):**  
  Has search icon left (`.r1-search-icon`) and clear `×` button right (`.r1-search-clear`).
- **Autocomplete Dropdown (`.r1-sec-dropdown`):**  
  `position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 200; max-height: 280px; overflow-y: auto; box-shadow: 0 8px 24px rgba(0,0,0,0.1);`
- **AMC Multi-Select Trigger (`.r1-amc-trigger`):**  
  Custom toggle element containing label text clamped via ellipsis, chevron arrow, and dropdown popover panel (`.r1-amc-panel`). Features "Select All" and "Clear" utility buttons in header.

---

## 7. RESPONSIVE BREAKPOINT INVENTORY

An exhaustive audit of `src/app/globals.css` reveals **eight distinct responsive breakpoints**:

```
[Desktop Ultra-wide]    >= 1441px    Full multi-column tables, unbounded layout margins
[Desktop Standard]      1025px - 1440px Container max-width clamped (1200px - 1760px)
[Tablet / Laptop]       <= 1024px    Line 7272: Container padding reduced to 1.5rem
[Tablet Landscape]      <= 960px     Line 5591: Footer transitions to 2-column layout
[Tablet Standard]       <= 900px     Line 2194: Report 1–4 filter bars wrap, title scales to 1.5rem
[Mobile / Tablet Trans] <= 768px     Line 7279: PRIMARY SWITCH: Desktop nav hidden, Hamburger shown,
                                     tables switch to touch-scroll, grids collapse to 1 column
[Filter Clamp]          <= 640px     Line 7496: Dropdowns clamp to 100vw - 2rem, sticky first table col
[Mobile Standard]       <= 600px     Line 2203: AMC triggers clamp to 120px, chart cards pad 1rem
[Mobile Compact]        <= 480px     Line 7589: 16px font inputs (iOS zoom prevention), single-column forms
```

### Detailed Breakpoint Behavior

#### 1. `@media (max-width: 1024px)`
- `.container` padding shrinks from `2rem` to `1.5rem`.
- Report 6 multi-select dropdown panels adapt to constrained tablet widths.

#### 2. `@media (max-width: 960px)`
- `.site-footer .footer-top` transitions from a 4-column layout (`grid-template-columns: 2fr 1fr 1fr 1fr`) to a 2-column layout (`grid-template-columns: 1fr 1fr`).

#### 3. `@media (max-width: 900px)`
- `.r1-page`, `.r2-page`: padding reduces to `1.25rem 1rem 3rem`.
- `.r1-title`, `.r2-title`: font size scales from `2rem` down to `1.5rem`.
- `.r1-filter-bar`: switches padding to `1rem` and gap to `0.75rem`.
- `.r1-select`, `.r1-select-fund`: min-width resets to `130px`.
- `.r1-chart-meta`: changes from `text-align: right` to `text-align: left`.
- `.r1-sec-card-primary`: flexes into column layout with `gap: 0.5rem`.

#### 4. `@media (max-width: 768px)` — The Primary Mobile Boundary
- **Navigation Transformation:**
  - `.desktop-nav-links` is set to `display: none !important`.
  - `.mobile-nav-toggle` is set to `display: flex !important` (44×44px accessible touch target).
  - Activates `.mobile-nav-drawer` inside `.mobile-nav-overlay` with sliding animation (`slideDown 0.25s`).
- **Sticky Navigation Bar:**
  - `.header` padding contracts to `1rem 0`.
  - `.global-reports-nav` sticky top coordinate adjusts from `73px` to `65px`.
  - `.global-reports-nav-inner` padding contracts to `0.35rem 1rem` with `gap: 0.25rem`.
  - `.global-nav-tab` reduces padding to `0.4rem 0.7rem`, font size to `0.8rem`.
- **Hero & Dashboard:**
  - `.hero h1` scales from `3.5rem` down to `2.25rem !important`.
  - `.dash-report-grid` collapses to `grid-template-columns: 1fr !important`.
- **Table Scrollability:**
  - `.r2-table-wrap`, `.r4-table-wrap`, `.r5-table-wrap`, `.r6-table-wrap`, `.profile-table-wrap` enforce:  
    `overflow-x: auto !important; -webkit-overflow-scrolling: touch !important; width: 100% !important;`
- **Profile Layout:**
  - `.profile-page` collapses to single-column; `.profile-hero` stacks avatar, info, and action button vertically.

#### 5. `@media (max-width: 640px)` — Dropdown & Filter Clamp
- **Filter Panels & Dropdown Anchors:**
  - Autocomplete dropdowns (`.r1-sec-dropdown`, `.r2-sec-dropdown`, `.r3-sec-dropdown`, etc.) and AMC selection panels (`.r1-amc-panel`, `.r2-amc-panel`) are clamped:  
    `width: 100% !important; max-width: calc(100vw - 2rem) !important; left: 0 !important; right: 0 !important; z-index: 250 !important;`
- **Full Width Filter Groups:**
  - `.r1-filter-group` through `.r6-filter-group` become `width: 100% !important; min-width: 100% !important;`
- **Sticky Table First Column:**
  - In Reports 2, 4, 5, and 6, the first table column (Security Name) freezes:  
    `position: sticky !important; left: 0 !important; z-index: 4 !important; background-color: var(--card-bg, #ffffff) !important; box-shadow: 2px 0 6px rgba(0, 0, 0, 0.08);`  
    `thead th:first-child` elevates to `z-index: 10 !important;`.
- **Chart Layout:**
  - `.r1-chart-hdr` stacks title and metadata vertically (`flex-direction: column; align-items: flex-start; gap: 0.5rem;`).
  - `.r1-chart-container` sets height to `300px !important; min-height: 280px !important;`.

#### 6. `@media (max-width: 600px)`
- `.r1-amc-trigger`, `.r1-amc-label-text`: max-width clamped to `120px` with ellipsis truncation.
- `.r1-chart-card`: padding contracts to `1rem 0.75rem 0.75rem`.
- `.site-footer .footer-top`: collapses to a single column (`grid-template-columns: 1fr;`).

#### 7. `@media (max-width: 480px)` — Compact Mobile Phones
- `.container` padding reduces to `0 1rem`.
- `.hero h1` scales down to `1.85rem !important`.
- **iOS Safari Zoom Prevention:**  
  All form fields enforce `font-size: 1rem !important; min-height: 46px !important;` (`.form-input`, `input[type="text"]`, `input[type="email"]`, `input[type="password"]`, `select`).
- **Full-Width Action Buttons:**  
  `.hero-cta .btn`, `.questionnaire-actions .btn`, `.profile-hero-right .btn` expand to `width: 100% !important; min-height: 48px !important;`.

---

## 8. DESKTOP DESIGN SPECIFICATION (> 900px / > 768px)

1. **Header & Navigation:**
   - Left: Wealthyneers brand logo image (44px height).
   - Right: Inline horizontal flex row (`.desktop-nav-links`): Links (`Dashboard`, `Build Wealth`), Account Pill (`.nav-profile-pill` with initials avatar circle), and Outline Logout button.
2. **Secondary Sub-Nav:**
   - Sticky bar at `top: 73px`. Displays 8 tabs (`Dashboard`, `Build Wealth`, `Reports 1–6`) with icons and descriptive subtitles (`Report 1: Quantity Trend`).
3. **Filter Bars:**
   - Single horizontal bar (`.r1-filter-bar`) using `flex-wrap: wrap; align-items: flex-end; gap: 1rem;`. Security search input expands with `flex: 1; min-width: 220px;`. Select boxes line up side-by-side.
4. **Data Visualizations:**
   - Recharts canvas renders at full card width with generous height (400px), 12 spaced X-axis labels, visible dots, hover crosshairs, and rich HTML tooltips (`.r1-tooltip`).
5. **Analytical Tables:**
   - Renders multi-column matrix views (e.g., Report 4 cross-sectional grid) across the full viewport width (up to 1760px).

---

## 9. TABLET DESIGN SPECIFICATION (769px – 900px / 1024px)

1. **Navigation:**
   - Retains desktop navbar on 769px–900px, but padding contracts. Sub-navigation tabs support smooth horizontal momentum scrolling.
2. **Page Containers:**
   - Page padding contracts to `1.25rem 1rem 3rem`.
   - Page titles scale down to `1.5rem`.
3. **Filter Organization:**
   - Filter groups wrap naturally into two balanced rows. Select menus shrink to `min-width: 130px`.
4. **Cards & Meta:**
   - Chart meta label (`Last 12 Months · All Securities...`) left-aligns beneath the chart title rather than floating to the right margin.
   - Security info card (`.r1-sec-card-primary`) stacks the security title above the ISIN pill.
5. **Tables:**
   - Table wrappers maintain natural scrolling boundaries.

---

## 10. MOBILE DESIGN SPECIFICATION (<= 768px / <= 640px / <= 480px)

1. **Header & Drawer:**
   - Desktop links disappear. Mobile hamburger icon (`☰` / `✕`) appears on the right.
   - Tapping hamburger triggers `.mobile-nav-overlay` with a full-width sliding card drawer containing:
     - Logged-in user profile pill with initials avatar.
     - Vertical list of high-touch 48px navigation rows with icons.
     - Full-width red outline Log Out button.
2. **Secondary Reports Bar:**
   - Pinned at `top: 65px`. Horizontally scrollable without visible scrollbars (`scrollbar-width: none;`). Tabs reduce in size to 38px height.
3. **Filters:**
   - Below 640px, each filter group expands to `width: 100% !important`.
   - The security autocomplete dropdown and AMC dropdown float as full-width overlays (`max-width: calc(100vw - 2rem)`).
4. **Chart Presentation:**
   - Recharts container scales to `height: 300px !important`.
   - Chart header stacks title above metadata.
   - Touch tapping on data points displays the `.r1-tooltip` modal card above the finger.
5. **Tables:**
   - Enforce `-webkit-overflow-scrolling: touch`. The first column (Stock Name) remains pinned to the left edge with a subtle drop shadow (`box-shadow: 2px 0 6px rgba(0,0,0,0.08)`) while the numerical months scroll horizontally beneath.

---

## 11. PAGE-BY-PAGE UI INVENTORY

| Route | Page Name | Key Components & Wrappers | Styling Paradigm | Responsive Implementation |
| :--- | :--- | :--- | :--- | :--- |
| `/` | **Landing Page** | `main`, `.hero`, `.reports`, `.report-card`, `.pricing`, `.cov-section` | Global CSS (`globals.css`) + `AMCFundCoverage.jsx` | Hero h1 scales `3.5rem` -> `2.25rem` -> `1.85rem`. Pricing & reports grids stack. |
| `/login` | **Subscriber Login** | `.auth-container`, `.auth-card`, `.form-group`, `.btn-primary` | Global CSS (`globals.css:527-608`) | Centered flex container; card max-width 400px; inputs enforce 16px on mobile. |
| `/signup` | **Account Creation** | `.auth-container`, `.auth-card`, `.form-group`, `.btn-primary` | Global CSS (`globals.css:527-608`) | Matches `/login` structure exactly. |
| `/forgot-password` | **Password Recovery** | `.auth-container`, `.auth-card`, `.form-group`, `.btn-primary` | Global CSS (`globals.css:527-608`) | Clean email submission form; alert message feedback. |
| `/reset-password` | **Set New Password** | `.auth-container`, `.auth-card`, `.form-group`, `.btn-primary` | Global CSS (`globals.css:527-608`) | Verifies auth recovery token; updates password. |
| `/dashboard` | **Dashboard Hub** | `.dash-page`, `.dash-subnav`, `.dash-content`, `.dash-report-grid` | Global CSS (`globals.css:1267-1632`) | Grid collapses from `repeat(auto-fill, minmax(280px, 1fr))` to `1fr` on <= 768px. |
| `/profile` | **User Profile & Plan** | `.profile-page`, `.profile-hero`, `.profile-grid`, `.profile-card` | Global CSS (`globals.css:5172-5590`) | Stacks into 1 column on <= 768px; table scrolls; avatar scales down on <= 480px. |
| `/report1` | **Quantity Trend** | `.r1-page`, `.r1-filter-bar`, `.r1-chart-card`, `Recharts` | Global CSS (`globals.css:1632-2208`) | Filter bar wraps at 900px, stacks at 640px; chart height to 300px. |
| `/report2` | **Activity Monitor** | `.r2-page`, `.r2-summary-grid`, `.r2-table-wrap`, `.r2-table` | Global CSS (`globals.css:2209-3053`) | Summary stat cards stack; table scrolls horizontally with frozen first col. |
| `/report3` | **AMC Intelligence** | `.r3-page`, `.r3-chart-card`, `Recharts`, `.r3-amc-legend` | Global CSS (`globals.css:3054-3700`) | Multi-line categorical comparison; search chip toggle; controls stack at 640px. |
| `/report4` | **Direction Matrix** | `.r4-page`, `.r4-summary-grid`, `.r4-table-wrap`, `.r4-matrix-table`| Global CSS (`globals.css:3701-4406`) | Wide matrix table (1760px container); sticky stock column on <= 640px. |
| `/report5` | **Breadth Rankings** | `.r5-page`, `.r5-summary-grid`, `.r5-table-wrap`, `.r5-ranking-table`| Global CSS (`globals.css:4407-5171`) | Buying & selling score pills; ranking filters; sticky stock column on <= 640px. |
| `/report6` | **7-Month Consensus** | `.r6-page`, `.r6-filter-card`, `.r6-table-wrap`, `.r6-table` | Global CSS (`globals.css:610-1266`) | Direction chips (`▲`, `▼`, `—`); multi-row filter card; sticky stock column. |
| `/invest` | **Build Wealth (Advisory)**| `.invest-page`, `.invest-hero`, `.invest-benefits-grid` | Global CSS (`globals.css:5758-6074`) | Guided mutual fund distribution overview; benefit cards stack into 1 column. |
| `/investor-profile` | **Questionnaire** | `.questionnaire-form`, `.q-section-card`, `.q-options-grid` | Global CSS (`globals.css:6075-6710`) | Multi-section risk profile questionnaire; multi-choice grids collapse to 1 col. |
| `/contact` | **Contact & Support** | `.legal-page`, `.legal-card`, `.contact-grid` | Global CSS (`globals.css:5608-5757`) | Grid collapses from 2 columns to 1 column on <= 640px. |
| `/terms`, `/privacy`, `/refund` | **Legal & Policy Pages** | `.legal-page`, `.legal-card`, `.legal-section` | Global CSS (`globals.css:5608-5710`) | Clean single-column reader cards (max-width 960px). |
| `/report-description/[id]` | **Static Preview Guides** | Inline scoped layout + `.btn-primary` | Mixed Scoped + Globals | High-resolution UI screenshots with feature breakdown. |

---

## 12. SHARED COMPONENT ARCHITECTURE & DEPENDENCIES

### 12.1 `src/app/components/AuthNav.jsx`
- **Props:** None (Self-contained client state subscriber).
- **Dependencies:** `@/lib/supabase`, `@/lib/subscriptionCache`, Next.js `usePathname`, `useRouter`, `Link`.
- **Rendered Output:**
  - Desktop nav links (`.desktop-nav-links`): Dashboard, Build Wealth, Profile pill, Log Out / Log In / Sign Up.
  - Mobile hamburger button (`.mobile-nav-toggle`): Displays on `<= 768px`.
  - Mobile drawer overlay (`.mobile-nav-overlay`): Displays full-height slide-out navigation when opened.
- **Risk Assessment:** **HIGH IMPACT**. Any alteration affects navigation on all 42 routes in the platform.

### 12.2 `src/app/components/ReportsNav.jsx`
- **Props:** None.
- **Dependencies:** Next.js `usePathname`, `Link`.
- **Rendered Output:** Sticky sub-navigation bar (`.global-reports-nav`) rendered on `/dashboard`, `/invest`, and `/report*`.
- **Features:** Auto-detects active route and adds `.global-nav-tab-active` and `.global-nav-active-pill`.
- **Risk Assessment:** **HIGH IMPACT**. Controls secondary routing across all report pages.

### 12.3 `src/app/components/ReportGuideModal.jsx`
- **Props:**
  - `isOpen` (`boolean`): Controls modal visibility.
  - `onClose` (`function`): Callback when overlay or close button is clicked.
  - `initialReportId` (`string`, e.g. `'report1'`): Active tab upon opening.
- **Dependencies:** React `useState`, `useEffect`.
- **Rendered Output:** Full-screen modal overlay (`.guide-modal-overlay`) with tab switcher (`.guide-tab-btn`) for Reports 1 through 6, displaying interactive control guides, key features, interpretation methodology, and practical use cases.
- **Risk Assessment:** **MEDIUM IMPACT**. Shared across all 6 reports via the "How To Use" button.

### 12.4 `src/app/components/AMCFundCoverage.jsx`
- **Props:** None.
- **Dependencies:** `@/lib/supabase`, `@/lib/subscriptionCache`.
- **Rendered Output:** Live searchable accordion listing all 25 AMCs and 391 funds. Rendered on the Home landing page (`/`).
- **Risk Assessment:** **MEDIUM IMPACT**. Standalone component on home page.

### 12.5 `src/app/components/Navbar.jsx`
- **Status:** **LEGACY / UNUSED**. Not imported in `layout.js` or any page route. Superseded by `AuthNav.jsx`.

---

## 13. REPORT 1 — DETAILED UI MAP (`src/app/report1/page.jsx`)

Report 1 (`/report1`) is the core longitudinal volume analysis tool. Below is the exact UI mapping:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ .r1-page                                                                    │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ .r1-header                                                              │ │
│ │   .report-badge ("Report 1")  +  .report-desc-btn ("How To Use")        │ │
│ │   h1.r1-title ("Mutual Fund Quantity Trend")                            │ │
│ │   p.r1-subtitle (Rolling 12-month description)                          │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ .r1-filter-bar                                                          │ │
│ │   [Search Security] [AMC Multi-Select] [Fund Name] [Rating] [Clear]     │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ (Optional) .r1-sec-card (Security Name, ISIN Pill, Alias Chips)          │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ .r1-chart-card                                                          │ │
│ │   .r1-chart-hdr: h2.r1-chart-title + .r1-chart-meta ("Last 12 Months") │ │
│ │   Recharts ResponsiveContainer (400px height, 300px mobile)             │ │
│ │     - LineChart, CartesianGrid, XAxis (12 months), YAxis (Formatted Qty)│ │
│ │     - Tooltip (Custom R1Tooltip), Line (connectNulls=false)             │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ .r1-notes-container                                                     │ │
│ │   .r1-help-row (💡 Holding Metric explanation)                          │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Component Inventory

| Element | JSX Location | CSS Selectors | Desktop (> 900px) | Tablet (<= 900px) | Mobile (<= 640px) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Badge & Guide Row** | `page.jsx:567-576` | `.report-badge-row`, `.report-badge`, `.report-desc-btn` | Inline row; pill badges | Inline row | Wrapped flex row |
| **Page Title** | `page.jsx:577` | `.r1-title` | `font-size: 2rem; font-weight: 700;` | `font-size: 1.5rem;` | `font-size: 1.5rem;` |
| **Subtitle** | `page.jsx:578-580` | `.r1-subtitle` | `font-size: 0.95rem; max-width: 760px; line-height: 1.6;` | Full width | `font-size: 0.9rem;` |
| **Filter Container** | `page.jsx:584` | `.r1-filter-bar` | Horizontal bar; `padding: 1.25rem 1.5rem; gap: 1rem;` | `padding: 1rem; gap: 0.75rem;` | Stacks; full-width |
| **Security Search** | `page.jsx:586-632` | `.r1-sec-group`, `.r1-search-input`, `.r1-sec-dropdown` | `flex: 1; min-width: 220px;` Dropdown anchored below | `flex: 1;` | `width: 100% !important;` Dropdown clamps to viewport |
| **Selected Chip** | `page.jsx:590-600` | `.r1-selected-chip`, `.r1-chip-text`, `.r1-chip-x` | Pill container, text ellipsis, circular remove btn | Pill container | Clamped max-width |
| **Security Info Card** | `page.jsx:689-722` | `.r1-sec-card`, `.r1-sec-card-primary`, `.r1-isin-pill` | Left teal border (4px); horizontal space-between | Stacks title and ISIN | Compact padding (`1rem`) |
| **AMC Multi-Select** | `page.jsx:635-641` | `.r1-amc-wrap`, `.r1-amc-trigger`, `.r1-amc-panel` | Custom select trigger; popover list | Label max-width 130px | Clamped width (`120px`), popover full-width |
| **Fund Name Select** | `page.jsx:643-656` | `.r1-select.r1-select-fund` | `min-width: 200px; max-width: 300px;` | `min-width: 130px;` | Full width |
| **Rating Select** | `page.jsx:658-671` | `.r1-select` | `min-width: 150px;` | `min-width: 130px;` | Full width |
| **Clear Filters Btn** | `page.jsx:674-685` | `.r1-clear-btn.btn.btn-outline` | Inline outline button | Inline button | Stretches to row width |
| **Chart Card** | `page.jsx:726` | `.r1-chart-card` | `padding: 1.5rem 1.5rem 1rem; border-radius: 0.75rem;` | Normal padding | `padding: 1rem 0.75rem 0.75rem;` |
| **Chart Header & Meta**| `page.jsx:727-739` | `.r1-chart-hdr`, `.r1-chart-title`, `.r1-chart-meta` | Title left, meta right (`text-align: right`) | Meta left-aligned | Stacks vertically (`gap: 0.5rem`) |
| **Recharts Canvas** | `page.jsx:748-812` | `ResponsiveContainer`, `LineChart`, `Line` | `height: 400px;` 12 months X-axis ticks | `height: 400px;` | `height: 300px !important; min-height: 280px !important;` |
| **Recharts Tooltip** | `page.jsx:125-137` | `.r1-tooltip`, `.r1-tooltip-date`, `.r1-tooltip-row` | White card, shadow, displays date & quantity | White card | Floats above touch location |
| **Holding Metric Row** | `page.jsx:818-822` | `.r1-notes-container`, `.r1-help-row` | Small muted help text (`0.82rem`) | Small help text | Full width; wraps naturally |

---

## 14. VISUAL INSPECTION FINDINGS & CROSS-DEVICE AUDIT

From comprehensive source code and layout inspection across target screen widths:

### 1. Ultra-wide Desktops (1920 × 1080)
- Containers center gracefully (`margin: 0 auto;`).
- Report 1 (`max-width: 1300px`) and Reports 2/5 (`max-width: 1440px`) maintain strict maximum boundaries, preventing line charts from over-stretching horizontally.
- Ample negative space flanks the content area.

### 2. Standard Desktops & Laptops (1440 × 900 & 1280 × 800)
- Optimal baseline layout.
- Filter bar sits on a single neat row without awkward wraps.
- Chart canvas displays all 12 calendar month labels (`Sep-2025` to `Aug-2026`) with generous breathing room between ticks.

### 3. Small Laptops & Landscape Tablets (1024 × 768)
- Hit by `@media (max-width: 1024px)`.
- Outer padding contracts to `1.5rem`.
- Report 1 filters remain inline; Reports 4 and 6 tables fit cleanly without clipping.

### 4. Portrait Tablets (820 × 1180 & 768 × 1024)
- Hit by `@media (max-width: 900px)` and `@media (max-width: 768px)`.
- Page title scales down to `1.5rem`.
- Filter bar wraps into two rows.
- On exactly 768px, desktop navigation links hide and the mobile toggle appears.
- Secondary reports tab bar enables touch-swipe scrolling.

### 5. Large Mobile Devices (430 × 932 & 414 × 896)
- Hit by `@media (max-width: 640px)`.
- Filter inputs stack full-width (`width: 100% !important`).
- Chart card contracts padding to `0.75rem`. Chart height locks to `300px`.
- Recharts X-axis dynamically spaces out the 12 month labels without collision.

### 6. Standard & Compact Mobile Devices (390 × 844 & 360 × 800)
- Hit by `@media (max-width: 480px)`.
- Form inputs enforce `font-size: 1rem !important` (16px), completely eliminating iOS Safari auto-zoom behavior on input focus.
- Hero buttons, questionnaire buttons, and modal footers stretch to full width for comfortable one-thumb ergonomics.

---

## 15. CSS SPECIFICITY & REGRESSION RISKS

An audit of `src/app/globals.css` identifies key specificity dynamics to respect:

1. **Broad Reset vs. Box Sizing (`globals.css:23-34`):**
   ```css
   * { box-sizing: border-box; margin: 0; padding: 0; }
   ```
   Global reset is clean and standard.

2. **Heavy Use of `!important` in Mobile Passes (`globals.css:7279-7717`):**
   - The "Comprehensive Responsive Design System Pass" (lines 7089–7717) uses `!important` on overrides (e.g., `.r1-filter-group { width: 100% !important; }`, `font-size: 1rem !important`).
   - **Risk:** Attempting to override styles for mobile inside individual page sections higher up in `globals.css` will fail because the mobile pass rules placed at lines 7279–7717 have both `!important` and source-order precedence.

3. **Duplicated / Layered Media Queries:**
   - Report 1 responsive rules exist at lines 2194–2207 (`@media (max-width: 900px)` and `@media (max-width: 600px)`).
   - Additional Report 1 mobile clamp rules exist at lines 7496–7586 (`@media (max-width: 640px)`).
   - **Rule:** Any future mobile adjustment to Report 1 must be cross-checked against **both** locations.

4. **Sticky Navigation Coordinates:**
   - `.header` is sticky at `top: 0; z-index: 100;` (height: 73px on desktop, ~65px on mobile).
   - `.global-reports-nav` is sticky at `top: 73px; z-index: 90;` (and `top: 65px;` on mobile).
   - **Rule:** If the global header height or padding is ever modified, the `top` offset of `.global-reports-nav` must be adjusted simultaneously to prevent overlap or a visible gap.

---

## 16. FUTURE MODIFICATION SAFETY MAP

To ensure incoming engineers do not inadvertently introduce regressions, files and components are categorized by blast radius:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HIGH IMPACT (Platform-Wide Blast Radius)                                    │
│ ─────────────────────────────────────────────────────────────────────────── │
│ • src/app/globals.css (:root tokens, lines 1-100, lines 7089-7717)          │
│ • src/app/layout.js (Root HTML, Global Header, ReportsNav, Footer)          │
│ • src/app/components/AuthNav.jsx (Session state, Desktop & Mobile Nav)      │
│ • src/app/components/ReportsNav.jsx (Secondary sticky tab bar)              │
│ • src/lib/supabase.js, src/lib/subscriptionCache.js (Auth & Entitlements)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MEDIUM IMPACT (Multi-Report & Shared Component Scope)                       │
│ ─────────────────────────────────────────────────────────────────────────── │
│ • src/app/components/ReportGuideModal.jsx (Used across Reports 1 to 6)      │
│ • src/app/components/AMCFundCoverage.jsx (Used on Landing Page)             │
│ • Shared table sticky-column rules (globals.css:7564-7586)                  │
│ • Razorpay integration (src/lib/razorpay.js, API verify routes)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LOW IMPACT (Isolated Page-Specific Scope)                                   │
│ ─────────────────────────────────────────────────────────────────────────── │
│ • src/app/report1/page.jsx (Report 1 logic, data query, Recharts mapping)   │
│ • Individual report pages (/report2, /report3, /report4, /report5, /report6)│
│ • Isolated landing sections (/invest, /investor-profile, /contact)          │
│ • Static legal pages (/terms, /privacy, /refund)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 17. REPORT 1 IMPLEMENTATION READINESS & SPECIFICATION

Report 1 has been successfully transitioned to the rolling 12-calendar-month architecture. The exact implementation details are documented below for technical audit:

### 1. Rolling 12-Calendar-Month Calculation
- **Anchor Logic (`getRolling12MonthBounds` & `get12CalendarMonths`):**
  Anchored globally to `MAX(portfolio_date)` from `fund_holdings` (currently `2026-08-01`).
  Integer arithmetic computes the 11-month preceding boundary:
  $$\text{Start Month} = 8 - 11 = -3 \implies \text{Month } 9 \text{ (September) of Year } (2026 - 1) = 2025$$
  Current window: **`2025-09-01` through `2026-08-01`** (exactly 12 calendar months).
- **Calendar Scaffolding:**
  Generates all 12 calendar month keys. Data rows returned from `get_report1_chart` are mapped to these keys. Missing periods are assigned `total_quantity: null`.
- **Interpolation Suppression:**
  Recharts `<Line connectNulls={false}>` ensures missing observation months render gaps rather than continuous straight lines.
- **Tooltip Handling:**
  `R1Tooltip` checks if `qty != null` and displays `"Not Reported"` when null.
- **Y-Axis Domain:**
  Filtered via `chartData.map(d => d.total_quantity).filter(q => q != null)` so JavaScript does not coerce `null` to `0` when determining `Math.min`.

### 2. Description Subtitle
Updated in `src/app/report1/page.jsx`:
> *"Track the total institutional holding quantity for any security across all AMCs, funds, and industry ratings over the latest 12 months of available portfolio data."*

### 3. Chart Metadata
Updated in `src/app/report1/page.jsx`:
> Displays `Last 12 Months · All Securities (Total Market Quantity)` or contextually appends the selected filters.

### 4. Disclaimer Purge
The former `.r1-disclaimer-card` element, its warning icon, header, and explanatory paragraph were **completely purged** from `src/app/report1/page.jsx`. No replacement card was added. The `.r1-help-row` ("💡 Holding Metric") is preserved.

---

## 18. RECOMMENDED CROSS-DEVICE VALIDATION CHECKLIST

When validating any future UI changes on Wealthyneers, follow this systematic multi-viewport protocol:

### Desktop Verification (> 1024px)
- [ ] Header logo renders cleanly without layout shift (`priority` loading enabled).
- [ ] Inline desktop navigation displays Dashboard, Build Wealth, Profile pill, and Logout button.
- [ ] Sticky secondary reports tab bar sits exactly flush beneath the main header (73px offset).
- [ ] Filter bars align horizontally with aligned baselines; dropdown options are legible.
- [ ] Recharts line charts render all 12 X-axis month ticks with no truncation.
- [ ] Hover tooltips follow the cursor smoothly with high-contrast text.

### Tablet Verification (768px – 1024px)
- [ ] Secondary reports tab bar allows horizontal swiping without scrollbar interference.
- [ ] Filter bar wraps into two balanced rows without overflowing container padding.
- [ ] Page titles scale gracefully (`1.5rem`).
- [ ] Wide tables scroll smoothly with touch momentum (`-webkit-overflow-scrolling: touch`).

### Mobile Verification (360px – 480px)
- [ ] Desktop navigation links are hidden; mobile hamburger button is visible and tappable (44×44px minimum target).
- [ ] Tapping hamburger opens slide-down drawer with user profile and clear navigation options.
- [ ] Tapping outside or hitting `Escape` cleanly dismisses the mobile drawer.
- [ ] Search autocomplete dropdowns expand full-width (`calc(100vw - 2rem)`) with zero horizontal page spill.
- [ ] Form input fields enforce `font-size: 1rem` (16px) on iOS Safari, eliminating unwanted auto-zoom.
- [ ] Action buttons (Subscribe, Apply, Submit) expand to full width (`100%`) with minimum 48px touch height.
- [ ] Footer columns stack vertically into a single column.
