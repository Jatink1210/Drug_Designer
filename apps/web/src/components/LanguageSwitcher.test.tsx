/**
 * Unit tests for LanguageSwitcher component
 */

import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LanguageSwitcher } from './LanguageSwitcher';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';

describe('LanguageSwitcher Component', () => {
  const renderWithI18n = (component: React.ReactElement) => {
    return render(
      <I18nextProvider i18n={i18n}>
        {component}
      </I18nextProvider>
    );
  };

  it('renders language switcher', () => {
    renderWithI18n(<LanguageSwitcher />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('displays current language', () => {
    renderWithI18n(<LanguageSwitcher />);
    expect(screen.getByText(/English/i)).toBeInTheDocument();
  });

  it('shows language options when clicked', () => {
    renderWithI18n(<LanguageSwitcher />);
    const button = screen.getByRole('button');
    
    fireEvent.click(button);
    expect(screen.getByText('English')).toBeInTheDocument();
    expect(screen.getByText('Español')).toBeInTheDocument();
  });

  it('changes language when option selected', () => {
    renderWithI18n(<LanguageSwitcher />);
    const button = screen.getByRole('button');
    
    fireEvent.click(button);
    const spanishOption = screen.getByText('Español');
    fireEvent.click(spanishOption);
    
    // Language should change
    expect(i18n.language).toBe('es');
  });

  it('closes dropdown after selection', () => {
    renderWithI18n(<LanguageSwitcher />);
    const button = screen.getByRole('button');
    
    fireEvent.click(button);
    const englishOption = screen.getByText('English');
    fireEvent.click(englishOption);
    
    // Dropdown should close
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
