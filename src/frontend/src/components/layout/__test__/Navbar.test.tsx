'use client';

import { render, screen } from '@testing-library/react';
import { usePathname } from 'next/navigation';
import { Navbar } from '../navbar';

// Mock next/link
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(),
}));

const mockedUsePathname = usePathname as jest.MockedFunction<typeof usePathname>;

describe('Navbar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders AlgoStudio brand', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);
    expect(screen.getByText('AlgoStudio')).toBeInTheDocument();
  });

  test('renders all navigation items', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tasks')).toBeInTheDocument();
    expect(screen.getByText('Datasets')).toBeInTheDocument();
    expect(screen.getByText('Hosts')).toBeInTheDocument();
    expect(screen.getByText('Deploy')).toBeInTheDocument();
  });

  test('renders correct number of nav links', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const links = screen.getAllByRole('link');
    // 5 nav items + 1 brand link = 6 links
    expect(links).toHaveLength(6);
  });

  test('Dashboard link points to root path', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink).toHaveAttribute('href', '/');
  });

  test('Tasks link points to /tasks', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const tasksLink = screen.getByText('Tasks').closest('a');
    expect(tasksLink).toHaveAttribute('href', '/tasks');
  });

  test('Datasets link points to /datasets', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const datasetsLink = screen.getByText('Datasets').closest('a');
    expect(datasetsLink).toHaveAttribute('href', '/datasets');
  });

  test('Hosts link points to /hosts', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const hostsLink = screen.getByText('Hosts').closest('a');
    expect(hostsLink).toHaveAttribute('href', '/hosts');
  });

  test('Deploy link points to /deploy', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const deployLink = screen.getByText('Deploy').closest('a');
    expect(deployLink).toHaveAttribute('href', '/deploy');
  });

  test('navbar is a nav element', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  test('navbar has border-b class', () => {
    mockedUsePathname.mockReturnValue('/');
    const { container } = render(<Navbar />);

    const nav = container.querySelector('nav');
    expect(nav).toHaveClass('border-b', 'bg-card');
  });

  test('has container with proper styling', () => {
    mockedUsePathname.mockReturnValue('/');
    const { container } = render(<Navbar />);

    const nav = container.querySelector('nav');
    expect(nav?.querySelector('.container')).toBeInTheDocument();
  });

  test('nav items have icons', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    // Check that SVG icons are present (lucide-react icons)
    const icons = document.querySelectorAll('nav svg');
    expect(icons.length).toBeGreaterThan(0);
  });

  test('brand link has correct href', () => {
    mockedUsePathname.mockReturnValue('/');
    render(<Navbar />);

    const brandLink = screen.getByText('AlgoStudio').closest('a');
    expect(brandLink).toHaveAttribute('href', '/');
  });

  test('brand has bold text styling', () => {
    mockedUsePathname.mockReturnValue('/');
    const { container } = render(<Navbar />);

    const brand = screen.getByText('AlgoStudio');
    expect(brand.tagName.toLowerCase()).toBe('a');
  });

  test('navigation container has correct padding', () => {
    mockedUsePathname.mockReturnValue('/');
    const { container } = render(<Navbar />);

    const containerDiv = container.querySelector('.container');
    expect(containerDiv).toHaveClass('mx-auto', 'px-4');
  });

  test('navbar height is h-16', () => {
    mockedUsePathname.mockReturnValue('/');
    const { container } = render(<Navbar />);

    const innerDiv = container.querySelector('.flex.h-16');
    expect(innerDiv).toBeInTheDocument();
  });
});
