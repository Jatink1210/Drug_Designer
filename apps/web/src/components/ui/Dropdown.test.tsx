/**
 * Unit tests for Dropdown component
 * 
 * Tests dropdown functionality including:
 * - Rendering and display
 * - Option selection
 * - Keyboard navigation
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { Dropdown } from './Dropdown';

describe('Dropdown Component', () => {
  const mockOptions = [
    { value: 'option1', label: 'Option 1' },
    { value: 'option2', label: 'Option 2' },
    { value: 'option3', label: 'Option 3' },
  ];

  const mockOnChange = jest.fn();

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  describe('Rendering', () => {
    it('should render dropdown with placeholder', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select an option"
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Select an option')).toBeInTheDocument();
    });

    it('should render dropdown with selected value', () => {
      render(
        <Dropdown
          options={mockOptions}
          value="option2"
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Option 2')).toBeInTheDocument();
    });

    it('should render disabled dropdown', () => {
      render(
        <Dropdown
          options={mockOptions}
          disabled
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      expect(dropdown).toBeDisabled();
    });
  });

  describe('Interaction', () => {
    it('should open dropdown on click', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        expect(screen.getByText('Option 1')).toBeVisible();
        expect(screen.getByText('Option 2')).toBeVisible();
        expect(screen.getByText('Option 3')).toBeVisible();
      });
    });

    it('should select option on click', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        const option2 = screen.getByText('Option 2');
        fireEvent.click(option2);
      });

      expect(mockOnChange).toHaveBeenCalledWith('option2');
    });

    it('should close dropdown after selection', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        const option1 = screen.getByText('Option 1');
        fireEvent.click(option1);
      });

      await waitFor(() => {
        expect(screen.queryByText('Option 2')).not.toBeVisible();
      });
    });

    it('should close dropdown on outside click', async () => {
      render(
        <div>
          <Dropdown
            options={mockOptions}
            placeholder="Select"
            onChange={mockOnChange}
          />
          <div data-testid="outside">Outside</div>
        </div>
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        expect(screen.getByText('Option 1')).toBeVisible();
      });

      const outside = screen.getByTestId('outside');
      fireEvent.click(outside);

      await waitFor(() => {
        expect(screen.queryByText('Option 1')).not.toBeVisible();
      });
    });
  });

  describe('Keyboard Navigation', () => {
    it('should open dropdown on Enter key', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      dropdown.focus();
      fireEvent.keyDown(dropdown, { key: 'Enter' });

      await waitFor(() => {
        expect(screen.getByText('Option 1')).toBeVisible();
      });
    });

    it('should navigate options with arrow keys', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        expect(screen.getByText('Option 1')).toBeVisible();
      });

      fireEvent.keyDown(dropdown, { key: 'ArrowDown' });
      fireEvent.keyDown(dropdown, { key: 'ArrowDown' });
      fireEvent.keyDown(dropdown, { key: 'Enter' });

      expect(mockOnChange).toHaveBeenCalledWith('option2');
    });

    it('should close dropdown on Escape key', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        expect(screen.getByText('Option 1')).toBeVisible();
      });

      fireEvent.keyDown(dropdown, { key: 'Escape' });

      await waitFor(() => {
        expect(screen.queryByText('Option 1')).not.toBeVisible();
      });
    });
  });

  describe('Search Functionality', () => {
    it('should filter options based on search input', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          searchable
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        const searchInput = screen.getByPlaceholderText('Search...');
        fireEvent.change(searchInput, { target: { value: 'Option 2' } });
      });

      await waitFor(() => {
        expect(screen.getByText('Option 2')).toBeVisible();
        expect(screen.queryByText('Option 1')).not.toBeInTheDocument();
        expect(screen.queryByText('Option 3')).not.toBeInTheDocument();
      });
    });

    it('should show "No results" when search has no matches', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          searchable
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        const searchInput = screen.getByPlaceholderText('Search...');
        fireEvent.change(searchInput, { target: { value: 'Nonexistent' } });
      });

      await waitFor(() => {
        expect(screen.getByText('No results found')).toBeVisible();
      });
    });
  });

  describe('Multi-select', () => {
    it('should allow multiple selections', async () => {
      const mockMultiChange = jest.fn();
      
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          multiple
          onChange={mockMultiChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        const option1 = screen.getByText('Option 1');
        const option2 = screen.getByText('Option 2');
        
        fireEvent.click(option1);
        fireEvent.click(option2);
      });

      expect(mockMultiChange).toHaveBeenCalledWith(['option1', 'option2']);
    });

    it('should display selected count in multi-select', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          multiple
          value={['option1', 'option2']}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('2 selected')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      expect(dropdown).toHaveAttribute('aria-haspopup', 'listbox');
      expect(dropdown).toHaveAttribute('aria-expanded', 'false');
    });

    it('should update aria-expanded when opened', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        expect(dropdown).toHaveAttribute('aria-expanded', 'true');
      });
    });

    it('should have accessible labels', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          label="Choose an option"
          onChange={mockOnChange}
        />
      );

      expect(screen.getByLabelText('Choose an option')).toBeInTheDocument();
    });

    it('should support screen reader announcements', async () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        const listbox = screen.getByRole('listbox');
        expect(listbox).toHaveAttribute('aria-label');
      });
    });
  });

  describe('Styling and Variants', () => {
    it('should apply error styling', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          error="This field is required"
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('This field is required')).toBeInTheDocument();
      const dropdown = screen.getByRole('button');
      expect(dropdown).toHaveClass('error');
    });

    it('should apply custom className', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          className="custom-dropdown"
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      expect(dropdown).toHaveClass('custom-dropdown');
    });

    it('should render with different sizes', () => {
      const { rerender } = render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          size="small"
          onChange={mockOnChange}
        />
      );

      let dropdown = screen.getByRole('button');
      expect(dropdown).toHaveClass('size-small');

      rerender(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          size="large"
          onChange={mockOnChange}
        />
      );

      dropdown = screen.getByRole('button');
      expect(dropdown).toHaveClass('size-large');
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          loading
          onChange={mockOnChange}
        />
      );

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should disable interaction when loading', () => {
      render(
        <Dropdown
          options={mockOptions}
          placeholder="Select"
          loading
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      expect(dropdown).toBeDisabled();
    });
  });

  describe('Custom Rendering', () => {
    it('should render custom option template', async () => {
      const customOptions = [
        { value: '1', label: 'Option 1', icon: '🔵' },
        { value: '2', label: 'Option 2', icon: '🟢' },
      ];

      render(
        <Dropdown
          options={customOptions}
          placeholder="Select"
          renderOption={(option) => (
            <span>
              {option.icon} {option.label}
            </span>
          )}
          onChange={mockOnChange}
        />
      );

      const dropdown = screen.getByRole('button');
      fireEvent.click(dropdown);

      await waitFor(() => {
        expect(screen.getByText('🔵 Option 1')).toBeVisible();
        expect(screen.getByText('🟢 Option 2')).toBeVisible();
      });
    });
  });
});
