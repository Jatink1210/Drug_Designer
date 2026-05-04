/**
 * Unit tests for Tabs component
 * 
 * Tests tabs functionality including:
 * - Rendering and display
 * - Tab switching
 * - Keyboard navigation
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { Tabs, TabList, Tab, TabPanel } from './Tabs';

describe('Tabs Component', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  describe('Rendering', () => {
    it('should render tabs with panels', () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
            <Tab>Tab 3</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
          <TabPanel>Content 3</TabPanel>
        </Tabs>
      );

      expect(screen.getByText('Tab 1')).toBeInTheDocument();
      expect(screen.getByText('Tab 2')).toBeInTheDocument();
      expect(screen.getByText('Tab 3')).toBeInTheDocument();
      expect(screen.getByText('Content 1')).toBeVisible();
    });

    it('should render first tab as active by default', () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tab1 = screen.getByText('Tab 1');
      expect(tab1).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByText('Content 1')).toBeVisible();
      expect(screen.queryByText('Content 2')).not.toBeVisible();
    });

    it('should render with default selected index', () => {
      render(
        <Tabs defaultIndex={1}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tab2 = screen.getByText('Tab 2');
      expect(tab2).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByText('Content 2')).toBeVisible();
    });
  });

  describe('Tab Switching', () => {
    it('should switch tabs on click', async () => {
      render(
        <Tabs onChange={mockOnChange}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tab2 = screen.getByText('Tab 2');
      fireEvent.click(tab2);

      await waitFor(() => {
        expect(screen.getByText('Content 2')).toBeVisible();
        expect(screen.queryByText('Content 1')).not.toBeVisible();
      });

      expect(mockOnChange).toHaveBeenCalledWith(1);
    });

    it('should not switch to disabled tab', () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab disabled>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tab2 = screen.getByText('Tab 2');
      fireEvent.click(tab2);

      expect(screen.getByText('Content 1')).toBeVisible();
      expect(screen.queryByText('Content 2')).not.toBeVisible();
    });

    it('should work in controlled mode', () => {
      const { rerender } = render(
        <Tabs index={0} onChange={mockOnChange}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      expect(screen.getByText('Content 1')).toBeVisible();

      const tab2 = screen.getByText('Tab 2');
      fireEvent.click(tab2);

      expect(mockOnChange).toHaveBeenCalledWith(1);

      // Manually update index (simulating parent component update)
      rerender(
        <Tabs index={1} onChange={mockOnChange}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      expect(screen.getByText('Content 2')).toBeVisible();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should navigate tabs with arrow keys', async () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
            <Tab>Tab 3</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
          <TabPanel>Content 3</TabPanel>
        </Tabs>
      );

      const tab1 = screen.getByText('Tab 1');
      tab1.focus();

      // Press ArrowRight to move to Tab 2
      fireEvent.keyDown(tab1, { key: 'ArrowRight' });

      await waitFor(() => {
        const tab2 = screen.getByText('Tab 2');
        expect(tab2).toHaveFocus();
        expect(screen.getByText('Content 2')).toBeVisible();
      });
    });

    it('should navigate backwards with ArrowLeft', async () => {
      render(
        <Tabs defaultIndex={1}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tab2 = screen.getByText('Tab 2');
      tab2.focus();

      fireEvent.keyDown(tab2, { key: 'ArrowLeft' });

      await waitFor(() => {
        const tab1 = screen.getByText('Tab 1');
        expect(tab1).toHaveFocus();
        expect(screen.getByText('Content 1')).toBeVisible();
      });
    });

    it('should wrap around at the end with ArrowRight', async () => {
      render(
        <Tabs defaultIndex={2}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
            <Tab>Tab 3</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
          <TabPanel>Content 3</TabPanel>
        </Tabs>
      );

      const tab3 = screen.getByText('Tab 3');
      tab3.focus();

      fireEvent.keyDown(tab3, { key: 'ArrowRight' });

      await waitFor(() => {
        const tab1 = screen.getByText('Tab 1');
        expect(tab1).toHaveFocus();
      });
    });

    it('should jump to first tab with Home key', async () => {
      render(
        <Tabs defaultIndex={2}>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
            <Tab>Tab 3</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
          <TabPanel>Content 3</TabPanel>
        </Tabs>
      );

      const tab3 = screen.getByText('Tab 3');
      tab3.focus();

      fireEvent.keyDown(tab3, { key: 'Home' });

      await waitFor(() => {
        const tab1 = screen.getByText('Tab 1');
        expect(tab1).toHaveFocus();
      });
    });

    it('should jump to last tab with End key', async () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
            <Tab>Tab 3</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
          <TabPanel>Content 3</TabPanel>
        </Tabs>
      );

      const tab1 = screen.getByText('Tab 1');
      tab1.focus();

      fireEvent.keyDown(tab1, { key: 'End' });

      await waitFor(() => {
        const tab3 = screen.getByText('Tab 3');
        expect(tab3).toHaveFocus();
      });
    });

    it('should skip disabled tabs when navigating', async () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab disabled>Tab 2</Tab>
            <Tab>Tab 3</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
          <TabPanel>Content 3</TabPanel>
        </Tabs>
      );

      const tab1 = screen.getByText('Tab 1');
      tab1.focus();

      fireEvent.keyDown(tab1, { key: 'ArrowRight' });

      await waitFor(() => {
        const tab3 = screen.getByText('Tab 3');
        expect(tab3).toHaveFocus();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tabList = screen.getByRole('tablist');
      expect(tabList).toBeInTheDocument();

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(2);

      const tab1 = tabs[0];
      expect(tab1).toHaveAttribute('aria-selected', 'true');
      expect(tab1).toHaveAttribute('aria-controls');

      const tabPanel = screen.getByRole('tabpanel');
      expect(tabPanel).toHaveAttribute('aria-labelledby');
    });

    it('should have proper tabindex values', () => {
      render(
        <Tabs>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tabs = screen.getAllByRole('tab');
      expect(tabs[0]).toHaveAttribute('tabindex', '0');
      expect(tabs[1]).toHaveAttribute('tabindex', '-1');
    });

    it('should support custom aria-label', () => {
      render(
        <Tabs>
          <TabList aria-label="Main navigation">
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tabList = screen.getByRole('tablist');
      expect(tabList).toHaveAttribute('aria-label', 'Main navigation');
    });
  });

  describe('Styling and Variants', () => {
    it('should apply custom className', () => {
      render(
        <Tabs className="custom-tabs">
          <TabList>
            <Tab>Tab 1</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
        </Tabs>
      );

      const tabs = screen.getByRole('tablist').parentElement;
      expect(tabs).toHaveClass('custom-tabs');
    });

    it('should render with different variants', () => {
      const { rerender } = render(
        <Tabs variant="line">
          <TabList>
            <Tab>Tab 1</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
        </Tabs>
      );

      let tabList = screen.getByRole('tablist');
      expect(tabList).toHaveClass('variant-line');

      rerender(
        <Tabs variant="enclosed">
          <TabList>
            <Tab>Tab 1</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
        </Tabs>
      );

      tabList = screen.getByRole('tablist');
      expect(tabList).toHaveClass('variant-enclosed');
    });

    it('should render with different orientations', () => {
      render(
        <Tabs orientation="vertical">
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tabList = screen.getByRole('tablist');
      expect(tabList).toHaveAttribute('aria-orientation', 'vertical');
    });
  });

  describe('Tab Icons', () => {
    it('should render tabs with icons', () => {
      render(
        <Tabs>
          <TabList>
            <Tab icon="🏠">Home</Tab>
            <Tab icon="⚙️">Settings</Tab>
          </TabList>
          <TabPanel>Home Content</TabPanel>
          <TabPanel>Settings Content</TabPanel>
        </Tabs>
      );

      expect(screen.getByText('🏠')).toBeInTheDocument();
      expect(screen.getByText('⚙️')).toBeInTheDocument();
    });
  });

  describe('Lazy Loading', () => {
    it('should lazy load tab panels', () => {
      render(
        <Tabs isLazy>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      // Content 2 should not be in DOM initially
      expect(screen.queryByText('Content 2')).not.toBeInTheDocument();

      const tab2 = screen.getByText('Tab 2');
      fireEvent.click(tab2);

      // Content 2 should now be in DOM
      expect(screen.getByText('Content 2')).toBeInTheDocument();
    });
  });

  describe('Manual Activation', () => {
    it('should support manual activation mode', async () => {
      render(
        <Tabs isManual>
          <TabList>
            <Tab>Tab 1</Tab>
            <Tab>Tab 2</Tab>
          </TabList>
          <TabPanel>Content 1</TabPanel>
          <TabPanel>Content 2</TabPanel>
        </Tabs>
      );

      const tab1 = screen.getByText('Tab 1');
      tab1.focus();

      // Arrow key should only move focus, not activate
      fireEvent.keyDown(tab1, { key: 'ArrowRight' });

      const tab2 = screen.getByText('Tab 2');
      expect(tab2).toHaveFocus();
      
      // Content should still be Content 1
      expect(screen.getByText('Content 1')).toBeVisible();

      // Press Enter to activate
      fireEvent.keyDown(tab2, { key: 'Enter' });

      await waitFor(() => {
        expect(screen.getByText('Content 2')).toBeVisible();
      });
    });
  });
});
