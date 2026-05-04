/**
 * Internationalization (i18n) Configuration
 * 
 * Task 16.1: Set up i18n framework
 * NFR-USE-002: Internationalization
 * 
 * This module configures react-i18next for multi-language support.
 * 
 * Features:
 * - English as initial language
 * - Architecture ready for future languages
 * - Scientific data always in English
 * - User-facing labels translatable
 * - Automatic language detection
 * - Fallback to English
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files
import enTranslations from './locales/en.json';

// Supported languages
export const SUPPORTED_LANGUAGES = {
  en: 'English',
  // Future languages can be added here:
  // es: 'Español',
  // fr: 'Français',
  // de: 'Deutsch',
  // zh: '中文',
  // ja: '日本語',
} as const;

export type SupportedLanguage = keyof typeof SUPPORTED_LANGUAGES;

// Default language
export const DEFAULT_LANGUAGE: SupportedLanguage = 'en';

// i18n configuration
i18n
  // Detect user language
  .use(LanguageDetector)
  // Pass the i18n instance to react-i18next
  .use(initReactI18next)
  // Initialize i18next
  .init({
    // Resources
    resources: {
      en: {
        translation: enTranslations,
      },
      // Future languages:
      // es: { translation: esTranslations },
      // fr: { translation: frTranslations },
    },

    // Fallback language
    fallbackLng: DEFAULT_LANGUAGE,

    // Supported languages
    supportedLngs: Object.keys(SUPPORTED_LANGUAGES),

    // Debug mode (disable in production)
    debug: import.meta.env.DEV,

    // Interpolation options
    interpolation: {
      escapeValue: false, // React already escapes values
    },

    // Detection options
    detection: {
      // Order of detection methods
      order: ['localStorage', 'navigator', 'htmlTag'],
      
      // Cache user language
      caches: ['localStorage'],
      
      // localStorage key
      lookupLocalStorage: 'drug-designer-language',
    },

    // React options
    react: {
      // Use Suspense for async loading
      useSuspense: true,
      
      // Bind i18n to component lifecycle
      bindI18n: 'languageChanged',
      bindI18nStore: '',
      
      // Trans component options
      transEmptyNodeValue: '',
      transSupportBasicHtmlNodes: true,
      transKeepBasicHtmlNodesFor: ['br', 'strong', 'i', 'em', 'code'],
    },

    // Namespace options
    defaultNS: 'translation',
    ns: ['translation'],

    // Key separator (use dots for nested keys)
    keySeparator: '.',

    // Nesting separator
    nsSeparator: ':',

    // Return empty string for missing keys in production
    returnEmptyString: !import.meta.env.DEV,

    // Return key if translation is missing (useful for development)
    returnNull: false,
  });

/**
 * Change the current language
 * 
 * @param language - Language code (e.g., 'en', 'es')
 */
export const changeLanguage = async (language: SupportedLanguage): Promise<void> => {
  await i18n.changeLanguage(language);
};

/**
 * Get the current language
 * 
 * @returns Current language code
 */
export const getCurrentLanguage = (): SupportedLanguage => {
  return i18n.language as SupportedLanguage;
};

/**
 * Check if a language is supported
 * 
 * @param language - Language code to check
 * @returns True if language is supported
 */
export const isLanguageSupported = (language: string): language is SupportedLanguage => {
  return language in SUPPORTED_LANGUAGES;
};

/**
 * Get translation for a key
 * 
 * @param key - Translation key
 * @param options - Interpolation options
 * @returns Translated string
 */
export const t = (key: string, options?: Record<string, unknown>): string => {
  return i18n.t(key, options);
};

/**
 * Check if a translation key exists
 * 
 * @param key - Translation key
 * @returns True if key exists
 */
export const hasTranslation = (key: string): boolean => {
  return i18n.exists(key);
};

// Export i18n instance
export default i18n;
