/**
 * Language Switcher Component
 * 
 * Task 16.1: Set up i18n framework
 * NFR-USE-002: Internationalization
 * 
 * Allows users to switch between supported languages.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  SUPPORTED_LANGUAGES,
  SupportedLanguage,
  changeLanguage,
  getCurrentLanguage,
} from '../i18n/config';

interface LanguageSwitcherProps {
  className?: string;
  variant?: 'dropdown' | 'buttons';
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({
  className = '',
  variant = 'dropdown',
}) => {
  const { i18n } = useTranslation();
  const currentLanguage = getCurrentLanguage();

  const handleLanguageChange = async (language: SupportedLanguage) => {
    await changeLanguage(language);
  };

  if (variant === 'buttons') {
    return (
      <div className={`language-switcher-buttons ${className}`}>
        {Object.entries(SUPPORTED_LANGUAGES).map(([code, name]) => (
          <button
            key={code}
            onClick={() => handleLanguageChange(code as SupportedLanguage)}
            className={`language-button ${
              currentLanguage === code ? 'active' : ''
            }`}
            aria-label={`Switch to ${name}`}
            aria-pressed={currentLanguage === code}
          >
            {code.toUpperCase()}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={`language-switcher-dropdown ${className}`}>
      <select
        value={currentLanguage}
        onChange={(e) =>
          handleLanguageChange(e.target.value as SupportedLanguage)
        }
        className="language-select"
        aria-label="Select language"
      >
        {Object.entries(SUPPORTED_LANGUAGES).map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
    </div>
  );
};

export default LanguageSwitcher;
