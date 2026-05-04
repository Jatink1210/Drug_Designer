/**
 * Unit tests for Accordion component
 * 
 * Tests accordion/collapsible functionality including:
 * - Rendering and display
 * - Expand/collapse states
 * - Multiple items
 * - Single vs multiple expansion
 * - Keyboard navigation
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Accordion, AccordionItem } from './Accordion';

describe('Accordion Component', () => {
  describe('Rendering', () => {
    it('should render accordion', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      expect(screen.getByText('Item 1')).toBeInTheDocument();
    });

    it('should render multiple items', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
          <AccordionItem title="Item 3">Content 3</AccordionItem>
        </Accordion>
      );
      
      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
      expect(screen.getByText('Item 3')).toBeInTheDocument();
    });

    it('should render with custom icons', () => {
      render(
        <Accordion>
          <AccordionItem
            title="Item 1"
            icon={<span data-testid="custom-icon">→</span>}
          >
            Content 1
          </AccordionItem>
        </Accordion>
      );
      
      expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
    });
  });

  describe('Expand/Collapse', () => {
    it('should be collapsed by default', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      expect(screen.queryByText('Content 1')).not.toBeVisible();
    });

    it('should expand on click', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      fireEvent.click(header);
      
      expect(screen.getByText('Content 1')).toBeVisible();
    });

    it('should collapse when clicked again', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      
      fireEvent.click(header);
      expect(screen.getByText('Content 1')).toBeVisible();
      
      fireEvent.click(header);
      expect(screen.queryByText('Content 1')).not.toBeVisible();
    });

    it('should call onChange when expanded', () => {
      const mockOnChange = jest.fn();
      render(
        <Accordion onChange={mockOnChange}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      fireEvent.click(header);
      
      expect(mockOnChange).toHaveBeenCalledWith([0]);
    });
  });

  describe('Single vs Multiple Expansion', () => {
    it('should allow only one item expanded by default', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
        </Accordion>
      );
      
      fireEvent.click(screen.getByText('Item 1'));
      expect(screen.getByText('Content 1')).toBeVisible();
      
      fireEvent.click(screen.getByText('Item 2'));
      expect(screen.getByText('Content 2')).toBeVisible();
      expect(screen.queryByText('Content 1')).not.toBeVisible();
    });

    it('should allow multiple items expanded when allowMultiple is true', () => {
      render(
        <Accordion allowMultiple>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
        </Accordion>
      );
      
      fireEvent.click(screen.getByText('Item 1'));
      fireEvent.click(screen.getByText('Item 2'));
      
      expect(screen.getByText('Content 1')).toBeVisible();
      expect(screen.getByText('Content 2')).toBeVisible();
    });

    it('should allow toggling items when allowToggle is true', () => {
      render(
        <Accordion allowToggle>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      
      fireEvent.click(header);
      expect(screen.getByText('Content 1')).toBeVisible();
      
      fireEvent.click(header);
      expect(screen.queryByText('Content 1')).not.toBeVisible();
    });
  });

  describe('Default Expanded Items', () => {
    it('should expand items by default when defaultIndex is set', () => {
      render(
        <Accordion defaultIndex={[0]}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
        </Accordion>
      );
      
      expect(screen.getByText('Content 1')).toBeVisible();
      expect(screen.queryByText('Content 2')).not.toBeVisible();
    });

    it('should expand multiple items when defaultIndex has multiple values', () => {
      render(
        <Accordion defaultIndex={[0, 1]} allowMultiple>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
        </Accordion>
      );
      
      expect(screen.getByText('Content 1')).toBeVisible();
      expect(screen.getByText('Content 2')).toBeVisible();
    });
  });

  describe('Controlled Mode', () => {
    it('should work in controlled mode', () => {
      const mockOnChange = jest.fn();
      const { rerender } = render(
        <Accordion index={[]} onChange={mockOnChange}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      expect(screen.queryByText('Content 1')).not.toBeVisible();
      
      fireEvent.click(screen.getByText('Item 1'));
      expect(mockOnChange).toHaveBeenCalledWith([0]);
      
      rerender(
        <Accordion index={[0]} onChange={mockOnChange}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      expect(screen.getByText('Content 1')).toBeVisible();
    });
  });

  describe('Disabled State', () => {
    it('should disable specific items', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1" disabled>Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      fireEvent.click(header);
      
      expect(screen.queryByText('Content 1')).not.toBeVisible();
    });

    it('should have disabled styling', () => {
      const { container } = render(
        <Accordion>
          <AccordionItem title="Item 1" disabled>Content 1</AccordionItem>
        </Accordion>
      );
      
      const item = container.querySelector('.accordion-item');
      expect(item).toHaveClass('disabled');
    });

    it('should disable entire accordion', () => {
      render(
        <Accordion disabled>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
        </Accordion>
      );
      
      fireEvent.click(screen.getByText('Item 1'));
      fireEvent.click(screen.getByText('Item 2'));
      
      expect(screen.queryByText('Content 1')).not.toBeVisible();
      expect(screen.queryByText('Content 2')).not.toBeVisible();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should navigate with arrow keys', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
          <AccordionItem title="Item 3">Content 3</AccordionItem>
        </Accordion>
      );
      
      const item1 = screen.getByText('Item 1');
      const item2 = screen.getByText('Item 2');
      
      item1.focus();
      expect(item1).toHaveFocus();
      
      fireEvent.keyDown(item1, { key: 'ArrowDown' });
      expect(item2).toHaveFocus();
    });

    it('should expand with Enter key', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      header.focus();
      
      fireEvent.keyDown(header, { key: 'Enter' });
      expect(screen.getByText('Content 1')).toBeVisible();
    });

    it('should expand with Space key', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      header.focus();
      
      fireEvent.keyDown(header, { key: ' ' });
      expect(screen.getByText('Content 1')).toBeVisible();
    });

    it('should navigate to first item with Home key', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
          <AccordionItem title="Item 3">Content 3</AccordionItem>
        </Accordion>
      );
      
      const item1 = screen.getByText('Item 1');
      const item3 = screen.getByText('Item 3');
      
      item3.focus();
      fireEvent.keyDown(item3, { key: 'Home' });
      
      expect(item1).toHaveFocus();
    });

    it('should navigate to last item with End key', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
          <AccordionItem title="Item 2">Content 2</AccordionItem>
          <AccordionItem title="Item 3">Content 3</AccordionItem>
        </Accordion>
      );
      
      const item1 = screen.getByText('Item 1');
      const item3 = screen.getByText('Item 3');
      
      item1.focus();
      fireEvent.keyDown(item1, { key: 'End' });
      
      expect(item3).toHaveFocus();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      const { container } = render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const button = screen.getByText('Item 1');
      expect(button).toHaveAttribute('aria-expanded', 'false');
      expect(button).toHaveAttribute('aria-controls');
    });

    it('should update aria-expanded when expanded', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const button = screen.getByText('Item 1');
      
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });

    it('should have role="region" on content', () => {
      render(
        <Accordion defaultIndex={[0]}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const content = screen.getByText('Content 1').parentElement;
      expect(content).toHaveAttribute('role', 'region');
    });

    it('should have aria-labelledby on content', () => {
      render(
        <Accordion defaultIndex={[0]}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const content = screen.getByText('Content 1').parentElement;
      expect(content).toHaveAttribute('aria-labelledby');
    });

    it('should have aria-disabled when disabled', () => {
      render(
        <Accordion>
          <AccordionItem title="Item 1" disabled>Content 1</AccordionItem>
        </Accordion>
      );
      
      const button = screen.getByText('Item 1');
      expect(button).toHaveAttribute('aria-disabled', 'true');
    });
  });

  describe('Animation', () => {
    it('should animate expansion', async () => {
      const { container } = render(
        <Accordion>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      fireEvent.click(header);
      
      const content = container.querySelector('.accordion-content');
      await waitFor(() => {
        expect(content).toHaveClass('expanding');
      });
    });

    it('should animate collapse', async () => {
      const { container } = render(
        <Accordion defaultIndex={[0]}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const header = screen.getByText('Item 1');
      fireEvent.click(header);
      
      const content = container.querySelector('.accordion-content');
      await waitFor(() => {
        expect(content).toHaveClass('collapsing');
      });
    });
  });

  describe('Variants', () => {
    it('should render default variant', () => {
      const { container } = render(
        <Accordion variant="default">
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const accordion = container.querySelector('.accordion');
      expect(accordion).toHaveClass('variant-default');
    });

    it('should render bordered variant', () => {
      const { container } = render(
        <Accordion variant="bordered">
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const accordion = container.querySelector('.accordion');
      expect(accordion).toHaveClass('variant-bordered');
    });

    it('should render filled variant', () => {
      const { container } = render(
        <Accordion variant="filled">
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const accordion = container.querySelector('.accordion');
      expect(accordion).toHaveClass('variant-filled');
    });
  });

  describe('Custom Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <Accordion className="custom-accordion">
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const accordion = container.querySelector('.accordion');
      expect(accordion).toHaveClass('custom-accordion');
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <Accordion style={{ margin: '20px' }}>
          <AccordionItem title="Item 1">Content 1</AccordionItem>
        </Accordion>
      );
      
      const accordion = container.querySelector('.accordion');
      expect(accordion).toHaveStyle({ margin: '20px' });
    });
  });
});
