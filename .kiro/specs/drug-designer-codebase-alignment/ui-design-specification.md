# UI Design Specification: Drug Designer Application
## Apple Design System Implementation

**Version:** 1.0
**Status:** Complete
**Based on:** DESIGN-apple.md principles + Drug_Designer.md requirements

---

## Executive Summary

This document provides a complete UI/UX design specification for the Drug Designer application, applying Apple's design principles (DESIGN-apple.md) to create a browser-native scientific research platform. The design emphasizes:

- **Evidence-first, not chat-first** - Scientific data takes visual priority
- **Provenance always visible** - Source attribution is never hidden
- **Contradictions exposed** - Conflicting evidence is highlighted, not flattened
- **Cinematic presentation** - Full-viewport sections with dramatic pacing
- **Single accent color** - Apple Blue (#0071e3) for all interactive elements
- **Optical typography** - SF Pro Display/Text with automatic sizing
- **Glass navigation** - Translucent dark nav with backdrop blur

---

## 1. Visual Theme & Color System

### 1.1 Color Palette

**Primary Colors:**
- **Pure Black** (`#000000`) - Hero sections, immersive product showcases
- **Light Gray** (`#f5f5f7`) - Alternate sections, informational areas
- **Near Black** (`#1d1d1f`) - Primary text on light backgrounds

**Interactive Colors:**
- **Apple Blue** (`#0071e3`) - PRIMARY accent for ALL interactive elements
- **Link Blue** (`#0066cc`) - Inline text links on light backgrounds
- **Bright Blue** (`#2997ff`) - Links on dark backgrounds

**Text Colors:**
- **White** (`#ffffff`) - Text on dark backgrounds
- **Near Black** (`#1d1d1f`) - Body text on light backgrounds
- **Black 80%** (`rgba(0, 0, 0, 0.8)`) - Secondary text
- **Black 48%** (`rgba(0, 0, 0, 0.48)`) - Tertiary text, disabled states

**Surface Colors (Dark Mode):**
- **Dark Surface 1** (`#272729`) - Card backgrounds
- **Dark Surface 2** (`#262628`) - Subtle variations
- **Dark Surface 3** (`#28282a`) - Elevated cards
- **Dark Surface 4** (`#2a2a2d`) - Highest elevation
- **Dark Surface 5** (`#242426`) - Deepest tone

**Semantic Colors (Scientific Context):**
- **Success Green** (`#34c759`) - Verified evidence, high confidence
- **Warning Orange** (`#ff9500`) - Degraded sources, medium confidence
- **Error Red** (`#ff3b30`) - Contradictions, failed runs, low confidence
- **Info Blue** (`#007aff`) - Informational badges, neutral states

### 1.2 Section Rhythm

Apply **binary light/dark alternation** for cinematic pacing:

```
Hero Section (Black #000000)
  ↓
Disease Intelligence (Light Gray #f5f5f7)
  ↓
Target Discovery (Black #000000)
  ↓
Evidence Explorer (Light Gray #f5f5f7)
  ↓
Graph Visualization (Black #000000)
  ↓
Dossier Generation (Light Gray #f5f5f7)
```

**Rules:**
- Each major workflow section alternates background color
- Dark sections feel immersive and premium
- Light sections feel open and informational
- No gradients, no textures - solid colors only

---

## 2. Typography System

### 2.1 Font Family

**SF Pro Display** - For 20px and above (headlines, large UI)
**SF Pro Text** - For 19px and below (body, small UI)

**Fallback Stack:**
```css
font-family: 'SF Pro Display', 'SF Pro Icons', 'Helvetica Neue', Helvetica, Arial, sans-serif;
```

### 2.2 Type Scale

| Role | Font | Size | Weight | Line Height | Letter Spacing | Use Case |
|------|------|------|--------|-------------|----------------|----------|
| **Display Hero** | SF Pro Display | 56px (3.50rem) | 600 | 1.07 | -0.28px | Module landing pages, major headlines |
| **Section Heading** | SF Pro Display | 40px (2.50rem) | 600 | 1.10 | normal | Feature section titles |
| **Page Title** | SF Pro Display | 32px (2.00rem) | 600 | 1.12 | -0.16px | Page headers |
| **Tile Heading** | SF Pro Display | 28px (1.75rem) | 400 | 1.14 | 0.196px | Card headlines, evidence tiles |
| **Card Title** | SF Pro Display | 21px (1.31rem) | 700 | 1.19 | 0.231px | Bold card headings |
| **Sub-heading** | SF Pro Display | 21px (1.31rem) | 400 | 1.19 | 0.231px | Regular card headings |
| **Body Large** | SF Pro Text | 19px (1.19rem) | 400 | 1.47 | -0.374px | Emphasized body text |
| **Body** | SF Pro Text | 17px (1.06rem) | 400 | 1.47 | -0.374px | Standard reading text |
| **Body Emphasis** | SF Pro Text | 17px (1.06rem) | 600 | 1.24 | -0.374px | Labels, emphasized text |
| **Button Large** | SF Pro Text | 18px (1.13rem) | 300 | 1.00 | normal | Large CTAs |
| **Button** | SF Pro Text | 17px (1.06rem) | 400 | 2.41 | normal | Standard buttons |
| **Link** | SF Pro Text | 14px (0.88rem) | 400 | 1.43 | -0.224px | "Learn more" links |
| **Caption** | SF Pro Text | 14px (0.88rem) | 400 | 1.29 | -0.224px | Secondary text, metadata |
| **Caption Bold** | SF Pro Text | 14px (0.88rem) | 600 | 1.29 | -0.224px | Emphasized captions |
| **Micro** | SF Pro Text | 12px (0.75rem) | 400 | 1.33 | -0.12px | Fine print, timestamps |
| **Micro Bold** | SF Pro Text | 12px (0.75rem) | 600 | 1.33 | -0.12px | Bold fine print |
| **Nano** | SF Pro Text | 10px (0.63rem) | 400 | 1.47 | -0.08px | Legal text, smallest size |

### 2.3 Typography Rules

1. **Optical Sizing Boundary:** SF Pro Display at 20px+, SF Pro Text below 20px
2. **Negative Letter-Spacing:** Apply at ALL sizes (not just headlines)
3. **Tight Line-Heights:** Headlines compress to 1.07-1.14 for impact
4. **Weight Restraint:** Use 300 (light), 400 (regular), 600 (semibold), 700 (bold) only
5. **No Wide Tracking:** SF Pro is designed to run tight at every size

---

## 3. Component Library

### 3.1 Buttons

#### Primary CTA (Apple Blue)
```css
background: #0071e3;
color: #ffffff;
padding: 8px 15px;
border-radius: 8px;
border: 1px solid transparent;
font: SF Pro Text, 17px, weight 400;
```
**Use:** Primary actions ("Run Analysis", "Generate Dossier", "Save Evidence")

#### Primary Dark
```css
background: #1d1d1f;
color: #ffffff;
padding: 8px 15px;
border-radius: 8px;
font: SF Pro Text, 17px, weight 400;
```
**Use:** Secondary CTAs on light backgrounds

#### Pill Link (Learn More / Explore)
```css
background: transparent;
color: #0066cc (light bg) | #2997ff (dark bg);
border-radius: 980px;
border: 1px solid #0066cc;
padding: 6px 18px;
font: SF Pro Text, 14px-17px;
```
**Use:** "Learn more", "Explore graph", "View details" - signature Apple link shape

#### Filter / Search Button
```css
background: #fafafc;
color: rgba(0, 0, 0, 0.8);
padding: 0px 14px;
border-radius: 11px;
border: 3px solid rgba(0, 0, 0, 0.04);
font: SF Pro Text, 14px;
```
**Use:** Search bars, filter controls, dropdown triggers

#### Icon Button (Media Control)
```css
background: rgba(210, 210, 215, 0.64);
color: rgba(0, 0, 0, 0.48);
border-radius: 50%;
width: 44px;
height: 44px;
```
**Use:** Play/pause, carousel arrows, expand/collapse

### 3.2 Cards & Containers

#### Evidence Card
```css
background: #f5f5f7 (light) | #272729 (dark);
border: none;
border-radius: 8px;
padding: 20px;
shadow: rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;
```
**Structure:**
- Source badge (top-left)
- Evidence title (28px SF Pro Display, weight 400)
- Evidence snippet (17px SF Pro Text)
- Provenance footer (12px SF Pro Text, rgba(0,0,0,0.48))
- Contradiction banner (if applicable)

#### Contradiction Banner
```css
background: rgba(255, 59, 48, 0.1);
border-left: 4px solid #ff3b30;
padding: 12px 16px;
border-radius: 4px;
```
**Content:**
- "⚠️ Contradiction Detected" (14px SF Pro Text, weight 600, #ff3b30)
- Conflicting claim summary (14px SF Pro Text)
- "View details" pill link

#### Confidence Bar
```css
height: 4px;
border-radius: 2px;
background: linear-gradient(to right, 
  #ff3b30 0%, 
  #ff9500 50%, 
  #34c759 100%);
```
**Indicator:**
- Position marker at confidence score (0-100%)
- Label above: "Confidence: 87%" (12px SF Pro Text, weight 600)

#### Provenance Badge
```css
background: rgba(0, 113, 227, 0.1);
color: #0071e3;
padding: 4px 10px;
border-radius: 12px;
font: SF Pro Text, 12px, weight 600;
```
**Content:** Source name + date (e.g., "PubMed • 2024")

### 3.3 Navigation

#### Global Navigation Bar
```css
position: sticky;
top: 0;
height: 48px;
background: rgba(0, 0, 0, 0.8);
backdrop-filter: saturate(180%) blur(20px);
z-index: 1000;
```
**Structure:**
- Logo (left, 17x48px)
- Nav links (center, 12px SF Pro Text, weight 400, white)
- Runtime indicator (right)
- User menu (right)

**Glass Effect:** The translucent dark + blur is non-negotiable - defines Apple web experience

#### Left Rail (Module Navigation)
```css
width: 240px;
background: #f5f5f7 (light) | #1d1d1f (dark);
border-right: 1px solid rgba(0, 0, 0, 0.1);
```
**Structure:**
- Module sections (Disease, Target, Evidence, Graph, etc.)
- Health indicators (green/yellow/red dots)
- Active state: Apple Blue (#0071e3) background

#### Health Strip (Top of Content)
```css
height: 32px;
background: #34c759 (healthy) | #ff9500 (degraded) | #ff3b30 (error);
color: #ffffff;
padding: 0 20px;
font: SF Pro Text, 12px, weight 600;
```
**Content:** "All sources healthy" | "2 sources degraded" | "Run failed"

### 3.4 Data Visualization

#### Force Graph (Knowledge Graph)
```css
background: #000000;
node-color: #0071e3 (default) | #34c759 (target) | #ff9500 (pathway);
edge-color: rgba(255, 255, 255, 0.2);
label-font: SF Pro Text, 10px, white;
```

#### Pathway Diagram
```css
background: #f5f5f7;
node-shape: rounded-rectangle (8px radius);
node-fill: #ffffff;
node-stroke: #0071e3 (2px);
edge-stroke: rgba(0, 0, 0, 0.3) (1px);
```

#### Structure Viewer (Mol*)
```css
background: #000000;
protein-color: #0071e3 (cartoon);
ligand-color: #34c759 (ball-and-stick);
surface-opacity: 0.3;
```

---

## 4. Page-by-Page Design Specifications

### 4.1 Disease Intelligence Page

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Global Nav (Glass, 48px)                        │
├─────────────────────────────────────────────────┤
│ Health Strip (32px)                             │
├─────────────────────────────────────────────────┤
│ Hero Section (Black #000000, full-viewport)     │
│   - "Disease Intelligence" (56px Display, white)│
│   - Search bar (centered, 600px wide)           │
│   - "Analyze Disease" CTA (Apple Blue pill)     │
└─────────────────────────────────────────────────┘
│ Results Section (Light Gray #f5f5f7)            │
│   - Normalized disease card                     │
│   - Candidate genes grid (3-column)             │
│   - Contradiction banner (if any)               │
└─────────────────────────────────────────────────┘
│ Evidence Section (Black #000000)                │
│   - Evidence cards (2-column)                   │
│   - Provenance badges                           │
│   - "Load more" pill link                       │
└─────────────────────────────────────────────────┘
```

**Components:**
- Disease search bar: Filter button style, 600px wide, centered
- Candidate gene card: 8px radius, shadow, confidence bar, provenance badge
- Contradiction banner: Red accent, left border, "View details" link

### 4.2 Target Prioritization Page

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Global Nav (Glass, 48px)                        │
├─────────────────────────────────────────────────┤
│ Health Strip (32px)                             │
├─────────────────────────────────────────────────┤
│ Hero Section (Light Gray #f5f5f7)               │
│   - "Target Prioritization" (40px Display)      │
│   - Filter controls (horizontal row)            │
│   - "Prioritize Targets" CTA (Apple Blue)       │
└─────────────────────────────────────────────────┘
│ Rankings Section (Black #000000)                │
│   - Target ranking table (full-width)           │
│   - Composite score visualization               │
│   - Score breakdown tooltips                    │
└─────────────────────────────────────────────────┘
│ Details Section (Light Gray #f5f5f7)            │
│   - Selected target details card                │
│   - Pathway memberships                         │
│   - GWAS associations                           │
│   - "Generate Dossier" CTA                      │
└─────────────────────────────────────────────────┘
```

**Components:**
- Target ranking row: Rank number (bold), gene symbol (21px Display), composite score (confidence bar), expand icon
- Score breakdown: Radar chart with 7 dimensions (GWAS, druggability, centrality, expression, safety, novelty, literature)
- Pathway badge: Pill shape, light blue background, pathway name

### 4.3 Evidence Explorer Page

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Global Nav (Glass, 48px)                        │
├─────────────────────────────────────────────────┤
│ Health Strip (32px)                             │
├─────────────────────────────────────────────────┤
│ Search Section (Black #000000, full-viewport)   │
│   - "Evidence Explorer" (56px Display, white)   │
│   - Multi-source search bar                     │
│   - Source family filters (pills)               │
└─────────────────────────────────────────────────┘
│ Results Section (Light Gray #f5f5f7)            │
│   - Evidence grid (3-column)                    │
│   - Contradiction indicators                    │
│   - Provenance badges                           │
│   - Confidence bars                             │
└─────────────────────────────────────────────────┘
│ Inspector Panel (Right drawer, 400px)           │
│   - Selected evidence details                   │
│   - Full provenance trace                       │
│   - Related evidence                            │
│   - "Save to project" CTA                       │
└─────────────────────────────────────────────────┘
```

**Components:**
- Evidence card: Source badge (top), title (28px), snippet (17px), provenance footer (12px), save icon
- Source filter pill: Transparent background, Apple Blue border, 980px radius
- Contradiction indicator: Red dot + "Contradicts 2 items" label

### 4.4 Knowledge Graph Page

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Global Nav (Glass, 48px)                        │
├─────────────────────────────────────────────────┤
│ Health Strip (32px)                             │
├─────────────────────────────────────────────────┤
│ Graph Canvas (Black #000000, full-viewport)     │
│   - Force-directed graph visualization          │
│   - Node labels (10px SF Pro Text, white)       │
│   - Edge weights (opacity-based)                │
│   - Zoom controls (bottom-right)                │
└─────────────────────────────────────────────────┘
│ Control Panel (Left overlay, 280px)             │
│   - "Knowledge Graph" (32px Display, white)     │
│   - Layout algorithm selector                   │
│   - Node type filters                           │
│   - Edge type filters                           │
│   - "Export graph" pill link                    │
└─────────────────────────────────────────────────┘
│ Inspector Panel (Right drawer, 400px)           │
│   - Selected node details                       │
│   - Connected nodes list                        │
│   - Pathway memberships                         │
│   - "Explore pathways" CTA                      │
└─────────────────────────────────────────────────┘
```

**Components:**
- Graph node: Circle (radius based on centrality), color by type, label on hover
- Graph edge: Line (width based on weight), color by type, dashed if predicted
- Control panel: Dark surface (#272729), 8px radius, shadow

### 4.5 Dossier Generation Page

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Global Nav (Glass, 48px)                        │
├─────────────────────────────────────────────────┤
│ Health Strip (32px)                             │
├─────────────────────────────────────────────────┤
│ Hero Section (Light Gray #f5f5f7)               │
│   - "Decision Dossier" (40px Display)           │
│   - Dossier title input (600px wide)            │
│   - Objective textarea                          │
│   - "Generate Dossier" CTA (Apple Blue)         │
└─────────────────────────────────────────────────┘
│ Preview Section (Black #000000)                 │
│   - Dossier preview card (centered, 800px)      │
│   - Section outline (left sidebar)              │
│   - Content preview (main area)                 │
│   - Provenance appendix (collapsible)           │
└─────────────────────────────────────────────────┘
│ Export Section (Light Gray #f5f5f7)             │
│   - Export format selector (PDF, DOCX, MD)      │
│   - "Download Dossier" CTA                      │
│   - "Share link" pill link                      │
└─────────────────────────────────────────────────┘
```

**Components:**
- Dossier preview card: White background, 8px radius, shadow, 800px wide
- Section outline: Left sidebar, 200px wide, section links (14px SF Pro Text)
- Provenance appendix: Collapsible section, gray background, evidence citations

---

## 5. Responsive Behavior

### 5.1 Breakpoints

| Name | Width | Key Changes |
|------|-------|-------------|
| Small Mobile | <360px | Minimum supported, single column |
| Mobile | 360-480px | Standard mobile layout |
| Mobile Large | 480-640px | Wider single column |
| Tablet Small | 640-834px | 2-column grids begin |
| Tablet | 834-1024px | Full tablet layout |
| Desktop Small | 1024-1070px | Standard desktop |
| Desktop | 1070-1440px | Full layout, max content width |
| Large Desktop | >1440px | Centered with margins |

### 5.2 Touch Targets

- Primary CTAs: 44px minimum height
- Navigation links: 48px height
- Icon buttons: 44x44px minimum
- Pill links: 36px minimum height

### 5.3 Collapsing Strategy

**Hero Headlines:**
- Desktop: 56px Display → Tablet: 40px → Mobile: 28px
- Maintain tight line-height proportionally

**Product Grids:**
- Desktop: 3-column → Tablet: 2-column → Mobile: 1-column stacked

**Navigation:**
- Desktop: Full horizontal nav → Mobile: Hamburger menu

**Section Backgrounds:**
- Maintain full-width color blocks at all breakpoints
- Cinematic rhythm never breaks

---

## 6. State Model & Truth Rules

### 6.1 Six States (Every Page Must Handle)

1. **Initial** - Before first interaction
2. **Loading** - During data fetch
3. **Empty** - No results found
4. **Degraded** - Partial results (some sources failed)
5. **Error** - Complete failure
6. **Success** - Full results

### 6.2 State Visualization

**Loading State:**
```
- Skeleton screens (gray rectangles, 8px radius)
- Spinner (Apple Blue, 32px, centered)
- "Loading..." text (17px SF Pro Text, rgba(0,0,0,0.48))
```

**Empty State:**
```
- Icon (48px, rgba(0,0,0,0.48))
- "No results found" (21px SF Pro Display, weight 600)
- Suggestion text (17px SF Pro Text)
- "Try again" CTA (Apple Blue pill)
```

**Degraded State:**
```
- Health strip (orange #ff9500)
- "2 sources degraded" message
- Partial results displayed
- "View degraded sources" pill link
```

**Error State:**
```
- Health strip (red #ff3b30)
- "Run failed" message
- Error details (collapsible)
- "Retry" CTA (Apple Blue)
```

### 6.3 Truth Rules

1. **Evidence Always Visible** - Every output shows source attribution
2. **Provenance Never Hidden** - Source lineage is always accessible
3. **Contradictions Exposed** - Conflicting evidence is highlighted
4. **Runtime Honest** - System shows which runtime is active (hosted/local)
5. **Health Truthful** - No fake green health indicators
6. **Confidence Explicit** - Every score is explainable

---

## 7. Accessibility (A11Y)

### 7.1 WCAG AA Compliance

**Color Contrast:**
- Text on light: 4.5:1 minimum (Near Black #1d1d1f on Light Gray #f5f5f7)
- Text on dark: 4.5:1 minimum (White #ffffff on Black #000000)
- Interactive elements: 3:1 minimum (Apple Blue #0071e3 on White)

**Focus Indicators:**
- All interactive elements: 2px solid #0071e3 outline
- Visible on keyboard navigation
- Never remove outline

**Touch Targets:**
- Minimum 44x44px for all interactive elements
- Adequate spacing between targets (8px minimum)

**Screen Reader Support:**
- Semantic HTML (nav, main, article, aside)
- ARIA labels for all icons
- ARIA live regions for dynamic content
- Skip links for navigation

### 7.2 Keyboard Navigation

- Tab order follows visual order
- Enter/Space activates buttons
- Escape closes modals/drawers
- Arrow keys navigate lists/grids

---

## 8. Animation & Motion

### 8.1 Transition Timing

```css
/* Standard easing */
transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);

/* Fast easing (hover) */
transition: all 0.15s cubic-bezier(0.4, 0.0, 0.2, 1);

/* Slow easing (page transitions) */
transition: all 0.5s cubic-bezier(0.4, 0.0, 0.2, 1);
```

### 8.2 Animation Principles

- **Subtle, not showy** - Animations support function, not decoration
- **Fast, not slow** - 150-300ms for most transitions
- **Natural easing** - Cubic bezier curves, not linear
- **Respect motion preferences** - Honor `prefers-reduced-motion`

---

## 9. Implementation Checklist

### Phase 1: Foundation (Week 1)
- [ ] Install SF Pro Display/Text fonts
- [ ] Create color token system (CSS variables)
- [ ] Implement typography scale (CSS classes)
- [ ] Build button component library
- [ ] Create card component library
- [ ] Implement glass navigation bar

### Phase 2: Components (Week 2)
- [ ] Evidence card with provenance badge
- [ ] Contradiction banner
- [ ] Confidence bar
- [ ] Health strip
- [ ] Inspector drawer
- [ ] Filter controls

### Phase 3: Pages (Weeks 3-4)
- [ ] Disease Intelligence page
- [ ] Target Prioritization page
- [ ] Evidence Explorer page
- [ ] Knowledge Graph page
- [ ] Dossier Generation page
- [ ] All other 55 pages

### Phase 4: States & Polish (Week 5)
- [ ] Implement 6 states for all pages
- [ ] Add loading skeletons
- [ ] Add empty states
- [ ] Add error states
- [ ] Add degraded states
- [ ] Accessibility audit (WCAG AA)

---

## 10. Design Tokens (CSS Variables)

```css
:root {
  /* Colors */
  --color-black: #000000;
  --color-light-gray: #f5f5f7;
  --color-near-black: #1d1d1f;
  --color-white: #ffffff;
  --color-apple-blue: #0071e3;
  --color-link-blue: #0066cc;
  --color-bright-blue: #2997ff;
  --color-success-green: #34c759;
  --color-warning-orange: #ff9500;
  --color-error-red: #ff3b30;
  
  /* Dark Surfaces */
  --color-dark-surface-1: #272729;
  --color-dark-surface-2: #262628;
  --color-dark-surface-3: #28282a;
  --color-dark-surface-4: #2a2a2d;
  --color-dark-surface-5: #242426;
  
  /* Typography */
  --font-display: 'SF Pro Display', 'SF Pro Icons', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --font-text: 'SF Pro Text', 'SF Pro Icons', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  
  /* Spacing */
  --space-2: 2px;
  --space-4: 4px;
  --space-6: 6px;
  --space-8: 8px;
  --space-12: 12px;
  --space-16: 16px;
  --space-20: 20px;
  --space-24: 24px;
  --space-32: 32px;
  --space-48: 48px;
  
  /* Border Radius */
  --radius-micro: 5px;
  --radius-standard: 8px;
  --radius-comfortable: 11px;
  --radius-large: 12px;
  --radius-pill: 980px;
  --radius-circle: 50%;
  
  /* Shadows */
  --shadow-card: rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;
  
  /* Transitions */
  --transition-fast: 0.15s cubic-bezier(0.4, 0.0, 0.2, 1);
  --transition-standard: 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
  --transition-slow: 0.5s cubic-bezier(0.4, 0.0, 0.2, 1);
}
```

---

## 11. Conclusion

This UI design specification provides a complete blueprint for implementing Apple's design principles in the Drug Designer application. The design emphasizes:

- **Scientific rigor** - Evidence, provenance, and contradictions are always visible
- **Visual clarity** - Binary light/dark rhythm, single accent color, optical typography
- **Functional beauty** - Every design decision supports scientific workflows
- **Accessibility** - WCAG AA compliance, keyboard navigation, screen reader support

**Implementation Priority:**
1. Foundation (colors, typography, tokens) - Week 1
2. Component library (buttons, cards, navigation) - Week 2
3. Page layouts (60 pages) - Weeks 3-4
4. States & polish (loading, empty, error, degraded) - Week 5

**Success Criteria:**
- All pages use SF Pro Display/Text with optical sizing
- Apple Blue (#0071e3) is the ONLY accent color
- Binary light/dark section rhythm applied throughout
- Glass navigation bar with backdrop blur
- All interactive elements have 2px #0071e3 focus rings
- WCAG AA color contrast ratios met
- 44px minimum touch targets
- 6 states handled on every page

This design system transforms Drug Designer into a world-class scientific research platform with Apple-level polish and attention to detail.
