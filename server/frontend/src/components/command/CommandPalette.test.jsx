import React from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { CommandPaletteProvider, CommandPaletteTrigger } from './CommandPalette';
import { isPaletteShortcut } from '@/hooks/useGlobalShortcut';

function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname + location.search}</output>;
}

function renderPalette() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <CommandPaletteProvider>
        <CommandPaletteTrigger />
        <Routes><Route path="*" element={<Where />} /></Routes>
      </CommandPaletteProvider>
    </MemoryRouter>,
  );
}

describe('CommandPalette', () => {
  it('recognises Ctrl+K and Cmd+K only', () => {
    expect(isPaletteShortcut({ ctrlKey: true, key: 'k' })).toBe(true);
    expect(isPaletteShortcut({ metaKey: true, key: 'K' })).toBe(true);
    expect(isPaletteShortcut({ key: 'k' })).toBe(false);
    expect(isPaletteShortcut({ ctrlKey: true, shiftKey: true, key: 'k' })).toBe(false);
  });

  it('opens on Ctrl+K, filters, and navigates with the keyboard', async () => {
    renderPalette();
    expect(screen.queryByRole('combobox')).toBeNull();
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    const input = await screen.findByRole('combobox', { name: 'Command, search or record' });
    expect(screen.getByRole('listbox', { name: 'Commands' })).toBeInTheDocument();

    fireEvent.change(input, { target: { value: 'gis workspace' } });
    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('data-command', 'search');
    expect(options[1]).toHaveTextContent('GIS Workspace');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    expect(input).toHaveAttribute('aria-activedescendant', 'command-option-1');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByTestId('where')).toHaveTextContent('/gis');
    expect(screen.queryByRole('combobox')).toBeNull();
  });

  it('runs query commands: coordinates jump the map', async () => {
    renderPalette();
    fireEvent.click(screen.getByRole('button', { name: /search & commands/i }));
    const input = await screen.findByRole('combobox');
    fireEvent.change(input, { target: { value: '18.2, -66.5' } });
    fireEvent.click(screen.getByRole('option', { name: /Jump the map to 18.2, -66.5/ }));
    expect(screen.getByTestId('where')).toHaveTextContent('/gis?lat=18.2&lon=-66.5');
  });

  it('reports when nothing matches instead of offering a dead command', async () => {
    renderPalette();
    fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = await screen.findByRole('combobox');
    expect(input).toHaveAttribute('aria-expanded', 'true');
    fireEvent.change(input, { target: { value: 'zz' } });
    expect(screen.getAllByRole('option')).toHaveLength(1); // only the search command
  });

  it('has no axe violations when open', async () => {
    const { baseElement } = renderPalette();
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    await screen.findByRole('combobox');
    expect(await axe(baseElement)).toHaveNoViolations();
  });
});
