# UI String Externalization Guide

## Overview

This guide provides instructions for externalizing hardcoded UI strings to translation files for internationalization support.

**Task**: 16.2 Externalize UI strings  
**Priority**: P2  
**Requirements**: NFR-USE-002 (Internationalization)

## Objectives

✅ All UI labels translatable  
✅ Scientific data remains in English  
✅ Language switcher functional  
✅ No hardcoded English strings in components

## What to Externalize

### ✅ DO Externalize

- **UI Labels**: "Name", "Description", "Status"
- **Button Text**: "Save", "Cancel", "Submit", "Delete"
- **Messages**: "Loading...", "Success!", "Error occurred"
- **Placeholders**: "Enter your email", "Search..."
- **Tooltips**: "Click to edit", "Download report"
- **Error Messages**: "Field is required", "Invalid format"
- **Help Text**: "This field is optional", "Maximum 100 characters"
- **Navigation**: "Home", "Projects", "Settings"
- **Status Text**: "Pending", "Completed", "Failed"
- **Confirmation Dialogs**: "Are you sure?", "This action cannot be undone"

### ❌ DON'T Externalize

- **Gene Names**: "FOXP3", "IL2RA", "CD4"
- **Protein IDs**: "P12345", "Q9Y6K9"
- **Chemical Formulas**: "C6H12O6", "H2O"
- **Database IDs**: "MONDO:0007915", "HP:0001250"
- **Technical Terms**: "p95 latency", "UUID", "API"
- **File Extensions**: ".json", ".csv", ".pdf"
- **HTTP Status Codes**: "404", "500"
- **Version Numbers**: "1.0.0", "v2.3.1"
- **URLs**: "https://example.com"
- **Regular Expressions**: "/^[A-Z]+$/"

## Migration Process

### Step 1: Identify Hardcoded Strings

Search for hardcoded strings in components:

```bash
# Find JSX strings
grep -r '"[A-Z]' apps/web/src/pages/
grep -r "'[A-Z]" apps/web/src/pages/

# Find template literals
grep -r '`[A-Z]' apps/web/src/pages/
```

### Step 2: Add to Translation File

Add the string to `apps/web/src/i18n/locales/en.json`:

```json
{
  "myModule": {
    "title": "My Module",
    "saveButton": "Save Changes",
    "cancelButton": "Cancel"
  }
}
```

### Step 3: Replace in Component

**Before**:
```typescript
function MyComponent() {
  return (
    <div>
      <h1>My Module</h1>
      <button>Save Changes</button>
      <button>Cancel</button>
    </div>
  );
}
```

**After**:
```typescript
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();
  
  return (
    <div>
      <h1>{t('myModule.title')}</h1>
      <button>{t('myModule.saveButton')}</button>
      <button>{t('myModule.cancelButton')}</button>
    </div>
  );
}
```

### Step 4: Test

```typescript
// Verify translation works
console.log(t('myModule.title')); // "My Module"

// Test language switching
await changeLanguage('es');
console.log(t('myModule.title')); // "Mi Módulo" (when Spanish is added)
```

## Examples by Component Type

### Buttons

**Before**:
```typescript
<button>Save</button>
<button>Cancel</button>
<button>Delete</button>
```

**After**:
```typescript
<button>{t('common.save')}</button>
<button>{t('common.cancel')}</button>
<button>{t('common.delete')}</button>
```

### Form Labels

**Before**:
```typescript
<label>Email Address</label>
<input placeholder="Enter your email" />
```

**After**:
```typescript
<label>{t('auth.login.email')}</label>
<input placeholder={t('auth.login.emailPlaceholder')} />
```

### Error Messages

**Before**:
```typescript
{error && <div>An error occurred</div>}
```

**After**:
```typescript
{error && <div>{t('errors.generic')}</div>}
```

### Validation Messages

**Before**:
```typescript
if (!email) {
  return "Email is required";
}
if (password.length < 8) {
  return "Password must be at least 8 characters";
}
```

**After**:
```typescript
if (!email) {
  return t('validation.required');
}
if (password.length < 8) {
  return t('validation.minLength', { min: 8 });
}
```

### Status Text

**Before**:
```typescript
const statusText = status === 'pending' ? 'Pending' : 
                   status === 'running' ? 'Running' : 
                   'Completed';
```

**After**:
```typescript
const statusText = t(`clinical.status.${status}`);
```

### Confirmation Dialogs

**Before**:
```typescript
if (confirm('Are you sure you want to delete this project?')) {
  deleteProject();
}
```

**After**:
```typescript
if (confirm(t('projects.deleteConfirm'))) {
  deleteProject();
}
```

### Table Headers

**Before**:
```typescript
<thead>
  <tr>
    <th>Name</th>
    <th>Status</th>
    <th>Created</th>
  </tr>
</thead>
```

**After**:
```typescript
<thead>
  <tr>
    <th>{t('common.name')}</th>
    <th>{t('common.status')}</th>
    <th>{t('common.created')}</th>
  </tr>
</thead>
```

### Navigation

**Before**:
```typescript
<nav>
  <a href="/projects">Projects</a>
  <a href="/disease">Disease Intelligence</a>
  <a href="/targets">Target Discovery</a>
</nav>
```

**After**:
```typescript
<nav>
  <a href="/projects">{t('navigation.projects')}</a>
  <a href="/disease">{t('navigation.disease')}</a>
  <a href="/targets">{t('navigation.targets')}</a>
</nav>
```

## Special Cases

### Dynamic Content with Interpolation

**Before**:
```typescript
<p>You have {count} items</p>
```

**After**:
```json
// en.json
{
  "items": {
    "count": "You have {{count}} items"
  }
}
```

```typescript
<p>{t('items.count', { count })}</p>
```

### Pluralization

**Before**:
```typescript
<p>{count} {count === 1 ? 'item' : 'items'}</p>
```

**After**:
```json
// en.json
{
  "items": "{{count}} item",
  "items_plural": "{{count}} items"
}
```

```typescript
<p>{t('items', { count })}</p>
```

### HTML Content

**Before**:
```typescript
<p>Welcome to <strong>Drug Designer</strong>!</p>
```

**After**:
```json
// en.json
{
  "welcome": {
    "message": "Welcome to <strong>Drug Designer</strong>!"
  }
}
```

```typescript
import { Trans } from 'react-i18next';

<Trans i18nKey="welcome.message" />
```

### Conditional Text

**Before**:
```typescript
<p>{isLoading ? 'Loading...' : 'Ready'}</p>
```

**After**:
```typescript
<p>{isLoading ? t('common.loading') : t('common.ready')}</p>
```

### Accessibility Labels

**Before**:
```typescript
<button aria-label="Close dialog">×</button>
```

**After**:
```typescript
<button aria-label={t('accessibility.closeDialog')}>×</button>
```

## Module-Specific Guidelines

### Disease Intelligence Module

Externalize:
- "Search Disease"
- "Candidate Genes"
- "Evidence"
- "Contradictions"

Keep in English:
- Gene symbols (e.g., "FOXP3")
- Disease IDs (e.g., "MONDO:0007915")
- Source names (e.g., "PubMed", "UniProt")

### Clinical Workflow Module

Externalize:
- Stage names ("EHR Ingestion", "Phenotype Clustering")
- Status text ("Pending", "Running", "Completed")
- Progress messages ("Processing...", "Complete")

Keep in English:
- Patient IDs (anonymized)
- Medical codes (ICD-10, SNOMED)
- Lab values and units

### Target Prioritization Module

Externalize:
- Column headers ("Gene", "Score", "Druggability")
- Filter labels ("Min Score", "Max Results")
- Action buttons ("Rank Targets", "Export")

Keep in English:
- Gene symbols
- Protein IDs
- Pathway names (KEGG, Reactome)

## Testing Checklist

### Before Deployment

- [ ] All UI labels are externalized
- [ ] No hardcoded English strings in components
- [ ] Scientific data remains in English
- [ ] Translation keys follow naming conventions
- [ ] Interpolation works correctly
- [ ] Pluralization works correctly
- [ ] Language switcher is functional
- [ ] Default language is English
- [ ] Fallback to English works
- [ ] localStorage persistence works

### Manual Testing

1. **Load application**: Verify default language is English
2. **Switch language**: Test language switcher (when other languages are added)
3. **Check all pages**: Verify all text is translated
4. **Test forms**: Verify labels, placeholders, validation messages
5. **Test errors**: Verify error messages are translated
6. **Test navigation**: Verify menu items are translated
7. **Test scientific data**: Verify gene names, IDs remain in English
8. **Clear localStorage**: Verify language detection works

## Common Pitfalls

### ❌ Pitfall 1: Translating Scientific Data

```typescript
// DON'T
<p>{t('genes.foxp3')}</p>  // Gene name should not be translated

// DO
<p>FOXP3</p>  // Keep gene names in English
```

### ❌ Pitfall 2: Hardcoded Strings in Logic

```typescript
// DON'T
if (status === "Pending") { ... }

// DO
if (status === "pending") { ... }  // Use lowercase keys
<p>{t(`status.${status}`)}</p>     // Translate for display
```

### ❌ Pitfall 3: Missing Interpolation

```typescript
// DON'T
<p>{t('items.count')}</p>  // Missing count parameter

// DO
<p>{t('items.count', { count: 5 })}</p>
```

### ❌ Pitfall 4: Incorrect Key Syntax

```typescript
// DON'T
<p>{t('common/save')}</p>  // Wrong separator

// DO
<p>{t('common.save')}</p>  // Use dot notation
```

## Automation Tools

### Find Hardcoded Strings

```bash
# Find potential hardcoded strings
grep -rn '"[A-Z][a-z]' apps/web/src/pages/ | grep -v 'import'

# Find strings in JSX
grep -rn '>[A-Z][a-z]' apps/web/src/pages/
```

### Validate Translation Keys

```typescript
// scripts/validate-translations.ts
import en from '../apps/web/src/i18n/locales/en.json';

function validateKeys(obj: any, path: string = '') {
  for (const [key, value] of Object.entries(obj)) {
    const fullPath = path ? `${path}.${key}` : key;
    
    if (typeof value === 'object') {
      validateKeys(value, fullPath);
    } else if (typeof value === 'string') {
      // Check for missing interpolation
      if (value.includes('{{') && !value.includes('}}')) {
        console.error(`Invalid interpolation in ${fullPath}`);
      }
    }
  }
}

validateKeys(en);
```

## Progress Tracking

### Modules to Externalize

- [ ] Disease Intelligence (2 pages)
- [ ] Target Discovery (2 pages)
- [ ] Evidence (4 pages)
- [ ] Graph/Pathways (5 pages)
- [ ] Structure/Design (3 pages)
- [ ] Translational (3 pages)
- [ ] Labs (6 pages)
- [ ] Reports/Dossiers (3 pages)
- [ ] Runtime (5 pages)
- [ ] Project Management (3 pages)
- [ ] Memory (3 pages)
- [ ] Operations (5 pages)
- [ ] Advanced (3 pages)

### Estimated Effort

- **Per page**: 15-30 minutes
- **Total pages**: 47 pages
- **Total effort**: 12-24 hours (1-2 days)

## Support

For questions or issues:
- Review i18n documentation in `apps/web/src/i18n/README.md`
- Check translation file `apps/web/src/i18n/locales/en.json`
- Contact frontend team

---

**Last Updated**: Task 16.2 Implementation  
**Version**: 1.0  
**Status**: Guide Complete (Implementation in Progress)
