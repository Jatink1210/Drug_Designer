# Internationalization (i18n) Guide

## Overview

The Drug Designer platform uses **react-i18next** for internationalization support. This allows the application to be translated into multiple languages while keeping scientific data in English.

**Task**: 16.1 Set up i18n framework  
**Priority**: P2  
**Requirements**: NFR-USE-002 (Internationalization)

## Architecture

### Current Support

- **English (en)**: Default and currently supported language
- **Future Languages**: Architecture ready for Spanish, French, German, Chinese, Japanese, etc.

### Key Principles

1. **User-facing labels are translatable**: All UI text, buttons, labels, messages
2. **Scientific data remains in English**: Gene names, protein IDs, chemical formulas, etc.
3. **Automatic language detection**: Detects user's browser language
4. **Fallback to English**: If translation is missing, falls back to English
5. **Persistent preference**: User's language choice is saved in localStorage

## Configuration

### Setup

The i18n configuration is in `apps/web/src/i18n/config.ts`:

```typescript
import i18n from './i18n/config';

// i18n is automatically initialized
```

### Supported Languages

Add new languages in `config.ts`:

```typescript
export const SUPPORTED_LANGUAGES = {
  en: 'English',
  es: 'Español',      // Spanish
  fr: 'Français',     // French
  de: 'Deutsch',      // German
  zh: '中文',         // Chinese
  ja: '日本語',       // Japanese
} as const;
```

## Usage

### In React Components

#### Using the Hook

```typescript
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();
  
  return (
    <div>
      <h1>{t('common.loading')}</h1>
      <button>{t('common.save')}</button>
    </div>
  );
}
```

#### With Interpolation

```typescript
const { t } = useTranslation();

// Simple interpolation
<p>{t('validation.minLength', { min: 8 })}</p>
// Output: "Must be at least 8 characters"

// Pluralization
<p>{t('time.minutes', { count: 5 })}</p>
// Output: "5 minutes"

<p>{t('time.minutes', { count: 1 })}</p>
// Output: "1 minute"
```

#### Trans Component (for HTML)

```typescript
import { Trans } from 'react-i18next';

<Trans i18nKey="welcome.message">
  Welcome to <strong>Drug Designer</strong>!
</Trans>
```

### Outside React Components

```typescript
import { t } from './i18n/config';

const message = t('common.error');
console.log(message); // "Error"
```

### Changing Language

```typescript
import { changeLanguage } from './i18n/config';

// Change to Spanish
await changeLanguage('es');
```

### Language Switcher Component

```typescript
import { LanguageSwitcher } from './components/LanguageSwitcher';

// Dropdown variant
<LanguageSwitcher variant="dropdown" />

// Button variant
<LanguageSwitcher variant="buttons" />
```

## Translation Files

### File Structure

```
apps/web/src/i18n/
├── config.ts              # i18n configuration
├── locales/
│   ├── en.json           # English translations
│   ├── es.json           # Spanish translations (future)
│   ├── fr.json           # French translations (future)
│   └── ...
└── README.md             # This file
```

### Translation File Format

Translations are organized hierarchically in JSON:

```json
{
  "common": {
    "loading": "Loading...",
    "save": "Save",
    "cancel": "Cancel"
  },
  "auth": {
    "login": {
      "title": "Login",
      "email": "Email",
      "password": "Password"
    }
  }
}
```

### Accessing Nested Keys

```typescript
t('common.loading')        // "Loading..."
t('auth.login.title')      // "Login"
t('auth.login.email')      // "Email"
```

## Adding New Translations

### Step 1: Add to English File

Add the key to `locales/en.json`:

```json
{
  "myFeature": {
    "title": "My Feature",
    "description": "This is my feature"
  }
}
```

### Step 2: Use in Component

```typescript
const { t } = useTranslation();

<h1>{t('myFeature.title')}</h1>
<p>{t('myFeature.description')}</p>
```

### Step 3: Add to Other Languages (Future)

When adding a new language, translate all keys:

```json
// locales/es.json
{
  "myFeature": {
    "title": "Mi Función",
    "description": "Esta es mi función"
  }
}
```

## Best Practices

### 1. Use Descriptive Keys

❌ Bad:
```json
{
  "text1": "Save",
  "text2": "Cancel"
}
```

✅ Good:
```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel"
  }
}
```

### 2. Group Related Translations

```json
{
  "auth": {
    "login": { ... },
    "register": { ... },
    "errors": { ... }
  }
}
```

### 3. Use Interpolation for Dynamic Content

❌ Bad:
```typescript
<p>You have {count} items</p>
```

✅ Good:
```json
{
  "items": {
    "count": "You have {{count}} items"
  }
}
```

```typescript
<p>{t('items.count', { count: 5 })}</p>
```

### 4. Use Pluralization

```json
{
  "items": "{{count}} item",
  "items_plural": "{{count}} items"
}
```

```typescript
t('items', { count: 1 })  // "1 item"
t('items', { count: 5 })  // "5 items"
```

### 5. Keep Scientific Data in English

❌ Don't translate:
- Gene names (e.g., "FOXP3", "IL2RA")
- Protein IDs (e.g., "P12345")
- Chemical formulas (e.g., "C6H12O6")
- Database IDs (e.g., "MONDO:0007915")
- Technical terms (e.g., "p95 latency")

✅ Do translate:
- UI labels (e.g., "Gene Name", "Protein ID")
- Button text (e.g., "Search", "Export")
- Messages (e.g., "Loading...", "Error occurred")
- Help text (e.g., "Enter a disease name")

### 6. Provide Context

Use comments in translation files:

```json
{
  "common": {
    // Button to save changes
    "save": "Save",
    
    // Button to cancel operation
    "cancel": "Cancel"
  }
}
```

### 7. Handle Missing Translations

In development, missing keys are shown as-is:
```typescript
t('missing.key')  // "missing.key"
```

In production, empty string is returned:
```typescript
t('missing.key')  // ""
```

## Testing

### Test Translation Keys

```typescript
import { hasTranslation } from './i18n/config';

if (hasTranslation('common.save')) {
  console.log('Translation exists');
}
```

### Test Language Switching

```typescript
import { changeLanguage, getCurrentLanguage } from './i18n/config';

// Change language
await changeLanguage('es');

// Verify
console.log(getCurrentLanguage()); // "es"
```

### Test Interpolation

```typescript
const result = t('validation.minLength', { min: 8 });
expect(result).toBe('Must be at least 8 characters');
```

## Adding a New Language

### Step 1: Create Translation File

Create `locales/es.json` (for Spanish):

```json
{
  "common": {
    "loading": "Cargando...",
    "save": "Guardar",
    "cancel": "Cancelar"
  }
}
```

### Step 2: Import in Config

```typescript
// config.ts
import esTranslations from './locales/es.json';

i18n.init({
  resources: {
    en: { translation: enTranslations },
    es: { translation: esTranslations },  // Add here
  },
});
```

### Step 3: Add to Supported Languages

```typescript
export const SUPPORTED_LANGUAGES = {
  en: 'English',
  es: 'Español',  // Add here
} as const;
```

### Step 4: Test

```typescript
await changeLanguage('es');
console.log(t('common.loading')); // "Cargando..."
```

## Troubleshooting

### Translation Not Showing

1. **Check key exists**: Verify key is in `en.json`
2. **Check syntax**: Ensure correct dot notation
3. **Check import**: Verify translation file is imported
4. **Clear cache**: Clear localStorage and reload

### Language Not Switching

1. **Check supported languages**: Verify language is in `SUPPORTED_LANGUAGES`
2. **Check translation file**: Ensure translation file exists and is imported
3. **Check localStorage**: Clear `drug-designer-language` key
4. **Check console**: Look for i18next errors

### Interpolation Not Working

1. **Check syntax**: Use `{{variable}}` not `{variable}`
2. **Check options**: Pass options object: `t('key', { variable: value })`
3. **Check escaping**: Ensure `escapeValue: false` in config

## Performance

### Lazy Loading (Future)

For large applications, load translations on demand:

```typescript
import i18n from 'i18next';
import Backend from 'i18next-http-backend';

i18n.use(Backend).init({
  backend: {
    loadPath: '/locales/{{lng}}.json',
  },
});
```

### Caching

Translations are cached in memory. To clear cache:

```typescript
i18n.reloadResources();
```

## Resources

- **react-i18next**: https://react.i18next.com/
- **i18next**: https://www.i18next.com/
- **Language Detector**: https://github.com/i18next/i18next-browser-languageDetector

## Support

For questions or issues:
- Check react-i18next documentation
- Review translation files in `locales/`
- Contact frontend team

---

**Last Updated**: Task 16.1 Implementation  
**Version**: 1.0  
**Status**: Complete
