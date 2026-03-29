# AlgoStudio Web Console - Project Structure

## Overview

Next.js 14+ App Router based Web Console for AlgoStudio AI Algorithm Platform.

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **UI Components**: shadcn/ui + Tailwind CSS
- **State Management**: React Query + Zustand
- **Charts**: Recharts
- **Terminal**: xterm.js
- **Language**: TypeScript

## Directory Structure

```
src/frontend/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── (main)/               # Main application routes
│   │   │   ├── layout.tsx       # Main layout with Navbar
│   │   │   ├── page.tsx         # Dashboard
│   │   │   ├── tasks/
│   │   │   │   ├── page.tsx     # Task list
│   │   │   │   └── [taskId]/
│   │   │   │       └── page.tsx # Task detail
│   │   │   ├── hosts/
│   │   │   │   ├── page.tsx     # Host monitoring
│   │   │   │   └── [nodeId]/
│   │   │   │       └── page.tsx # Node detail
│   │   │   └── deploy/
│   │   │       └── page.tsx     # Worker deployment
│   │   ├── api/
│   │   │   └── proxy/           # Server-side API proxy
│   │   │       ├── tasks/
│   │   │       │   └── route.ts
│   │   │       └── hosts/
│   │   │           └── route.ts
│   │   ├── layout.tsx           # Root layout
│   │   └── globals.css          # Global styles + CSS variables
│   │
│   ├── components/
│   │   ├── ui/                  # shadcn/ui base components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   └── table.tsx
│   │   ├── dashboard/           # Dashboard components
│   │   │   └── stats-card.tsx
│   │   ├── layout/              # Layout components
│   │   │   └── navbar.tsx
│   │   └── providers.tsx        # React Query provider
│   │
│   ├── hooks/                   # React Query hooks
│   │   ├── use-tasks.ts
│   │   └── use-hosts.ts
│   │
│   ├── lib/                     # Utilities
│   │   ├── api.ts               # API client
│   │   └── utils.ts             # cn() utility
│   │
│   └── types/                   # TypeScript types
│       ├── task.ts
│       ├── host.ts
│       └── api.ts
│
├── public/                      # Static assets
├── .env.local                   # Environment variables
├── next.config.js               # Next.js config
├── tailwind.config.ts           # Tailwind config
├── tsconfig.json                # TypeScript config
├── postcss.config.js            # PostCSS config
└── components.json              # shadcn/ui config
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview stats, cluster status, recent tasks |
| `/tasks` | Tasks | Task list with filtering |
| `/tasks/[taskId]` | Task Detail | Task details with progress |
| `/hosts` | Hosts | Cluster node monitoring |
| `/hosts/[nodeId]` | Node Detail | Individual node GPU info |
| `/deploy` | Deploy | Worker node deployment |

## API Integration

The frontend uses server-side API proxy routes to avoid exposing API keys on the client:
- `/api/proxy/tasks` - Proxies to FastAPI `/api/tasks`
- `/api/proxy/hosts` - Proxies to FastAPI `/api/hosts`

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI server URL (default: http://localhost:8000) |
| `API_KEY` | Backend API key (server-side only) |
