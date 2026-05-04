# Apple-Style Component Library

**Task 7.3 Implementation** - FR-UI-003

## Components

### Button
- Primary CTA buttons (Apple Blue background, white text, 8px padding, 8px border-radius)
- Pill links (transparent background, Apple Blue border, 980px border-radius)
- 6-state model: Initial, Loading, Success, Error, Disabled
- Variants: Primary, Secondary, Pill, Ghost, Icon
- Sizes: Small (36px), Medium (44px), Large (52px)

### Card
- Evidence cards (light gray background, 8px border-radius, shadow)
- 6-state model: Initial, Loading, Empty, Degraded, Error, Success
- Variants: Default, Evidence, Elevated, Outlined, Glass
- Interactive with hover effects
- Optional header and footer sections

### Navigation
- Glass navigation (translucent dark nav with backdrop blur)
- Sticky/Fixed/Static positioning
- Responsive with mobile menu
- Active states and notification badges
- Keyboard accessible

## Usage

```tsx
import { Button, Card, Navigation } from '@/components/ui';

// Button
<Button variant="primary">Get Started</Button>
<Button variant="pill">Learn More</Button>

// Card
<Card variant="evidence" state="loading" />
<Card variant="glass" interactive onClick={handleClick}>Content</Card>

// Navigation
<Navigation
  variant="glass"
  items={[
    { label: 'Home', href: '/', active: true },
    { label: 'Projects', href: '/projects', badge: 3 },
  ]}
/>
```

## Accessibility

All components are WCAG AA compliant with:
- Keyboard navigation
- Screen reader support
- Focus indicators
- Touch-friendly sizes (44px minimum)
- Proper ARIA labels

## Design System Integration

Components use:
- SF Pro typography (Task 7.1)
- Binary light/dark color system (Task 7.2)
- Apple Blue (#0071e3) for all interactive elements
- 8px border-radius for consistency
- Smooth transitions (200ms ease-in-out)
