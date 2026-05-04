/**
 * Unit tests for Tooltip component
 * 
 * Tests tooltip functionality including:
 * - Rendering and display
 * - Positioning
 * - Hover interactions
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { Tooltip } from './Tooltip';

describe('Tooltip Component', () => {
  describe('Rendering', () => {
    it('should render children without tooltip initially', () => {
      render(
        <Tooltip content="Tooltip text">
          <button>Hover me</button>
        </Tooltip>
      );

      expect(screen.getByText('Hover me')).toBeInTheDocument();
      expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();
    });

    it('should show tooltip on hover', async () => {
      render(
        <Tooltip content="Tooltip text">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        expect(screen.getByText('Tooltip text')).toBeVisible();
      });
    });

    it('should hide tooltip on mouse leave', async () => {
      render(
        <Tooltip content="Tooltip text">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        expect(screen.getByText('Tooltip text')).toBeVisible();
      });

      fireEvent.mouseLeave(button);

      await waitFor(() => {
        expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();
      });
    });

    it('should render with JSX content', async () => {
      render(
        <Tooltip content={<div><strong>Bold</strong> text</div>}>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        expect(screen.getByText('Bold')).toBeVisible();
        expect(screen.getByText('text')).toBeVisible();
      });
    });
  });

  describe('Positioning', () => {
    it('should render tooltip at top position', async () => {
      render(
        <Tooltip content="Tooltip text" position="top">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('position-top');
      });
    });

    it('should render tooltip at bottom position', async () => {
      render(
        <Tooltip content="Tooltip text" position="bottom">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('position-bottom');
      });
    });

    it('should render tooltip at left position', async () => {
      render(
        <Tooltip content="Tooltip text" position="left">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('position-left');
      });
    });

    it('should render tooltip at right position', async () => {
      render(
        <Tooltip content="Tooltip text" position="right">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('position-right');
      });
    });
  });

  describe('Delay', () => {
    it('should show tooltip after delay', async () => {
      jest.useFakeTimers();

      render(
        <Tooltip content="Tooltip text" delay={500}>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      // Should not be visible immediately
      expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();

      // Fast-forward time
      jest.advanceTimersByTime(500);

      await waitFor(() => {
        expect(screen.getByText('Tooltip text')).toBeVisible();
      });

      jest.useRealTimers();
    });

    it('should cancel tooltip if mouse leaves before delay', async () => {
      jest.useFakeTimers();

      render(
        <Tooltip content="Tooltip text" delay={500}>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      // Leave before delay completes
      jest.advanceTimersByTime(250);
      fireEvent.mouseLeave(button);

      jest.advanceTimersByTime(500);

      expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();

      jest.useRealTimers();
    });
  });

  describe('Trigger Modes', () => {
    it('should show tooltip on click when trigger is click', async () => {
      render(
        <Tooltip content="Tooltip text" trigger="click">
          <button>Click me</button>
        </Tooltip>
      );

      const button = screen.getByText('Click me');
      
      // Hover should not show tooltip
      fireEvent.mouseEnter(button);
      expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();

      // Click should show tooltip
      fireEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Tooltip text')).toBeVisible();
      });
    });

    it('should show tooltip on focus when trigger is focus', async () => {
      render(
        <Tooltip content="Tooltip text" trigger="focus">
          <button>Focus me</button>
        </Tooltip>
      );

      const button = screen.getByText('Focus me');
      
      fireEvent.focus(button);

      await waitFor(() => {
        expect(screen.getByText('Tooltip text')).toBeVisible();
      });

      fireEvent.blur(button);

      await waitFor(() => {
        expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();
      });
    });

    it('should always show tooltip when trigger is manual', () => {
      render(
        <Tooltip content="Tooltip text" trigger="manual" visible={true}>
          <button>Button</button>
        </Tooltip>
      );

      expect(screen.getByText('Tooltip text')).toBeVisible();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', async () => {
      render(
        <Tooltip content="Tooltip text">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      expect(button).toHaveAttribute('aria-describedby');

      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text');
        expect(tooltip).toHaveAttribute('role', 'tooltip');
      });
    });

    it('should be keyboard accessible', async () => {
      render(
        <Tooltip content="Tooltip text">
          <button>Focus me</button>
        </Tooltip>
      );

      const button = screen.getByText('Focus me');
      button.focus();

      await waitFor(() => {
        expect(screen.getByText('Tooltip text')).toBeVisible();
      });
    });

    it('should support aria-label override', async () => {
      render(
        <Tooltip content="Tooltip text" ariaLabel="Custom label">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text');
        expect(tooltip).toHaveAttribute('aria-label', 'Custom label');
      });
    });
  });

  describe('Styling', () => {
    it('should apply custom className', async () => {
      render(
        <Tooltip content="Tooltip text" className="custom-tooltip">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('custom-tooltip');
      });
    });

    it('should render with dark theme', async () => {
      render(
        <Tooltip content="Tooltip text" theme="dark">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('theme-dark');
      });
    });

    it('should render with light theme', async () => {
      render(
        <Tooltip content="Tooltip text" theme="light">
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('theme-light');
      });
    });

    it('should render with arrow', async () => {
      render(
        <Tooltip content="Tooltip text" arrow>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const arrow = screen.getByTestId('tooltip-arrow');
        expect(arrow).toBeInTheDocument();
      });
    });
  });

  describe('Max Width', () => {
    it('should apply max width', async () => {
      render(
        <Tooltip content="Very long tooltip text that should wrap" maxWidth={200}>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText(/Very long tooltip text/).parentElement;
        expect(tooltip).toHaveStyle({ maxWidth: '200px' });
      });
    });
  });

  describe('Disabled State', () => {
    it('should not show tooltip when disabled', async () => {
      render(
        <Tooltip content="Tooltip text" disabled>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        expect(screen.queryByText('Tooltip text')).not.toBeInTheDocument();
      }, { timeout: 1000 });
    });
  });

  describe('Portal Rendering', () => {
    it('should render tooltip in portal', async () => {
      render(
        <Tooltip content="Tooltip text" usePortal>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text');
        expect(tooltip.parentElement?.parentElement).toHaveAttribute('id', 'tooltip-portal');
      });
    });
  });

  describe('Animation', () => {
    it('should animate tooltip entrance', async () => {
      render(
        <Tooltip content="Tooltip text" animated>
          <button>Hover me</button>
        </Tooltip>
      );

      const button = screen.getByText('Hover me');
      fireEvent.mouseEnter(button);

      await waitFor(() => {
        const tooltip = screen.getByText('Tooltip text').parentElement;
        expect(tooltip).toHaveClass('animate-in');
      });
    });
  });
});
