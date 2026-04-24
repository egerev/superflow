# Next.js Greenfield Template

## Directory Structure
```
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   └── .gitkeep
│   └── lib/
│       └── .gitkeep
├── public/
│   └── .gitkeep
├── tests/
│   └── example.test.ts
├── .gitignore
├── .env.example
├── package.json
├── tsconfig.json
├── next.config.ts
├── README.md
└── CLAUDE.md
```

## package.json
```json
{
  "name": "{project_name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "next lint",
    "format": "prettier --write ."
  },
  "dependencies": {
    "next": "^15",
    "react": "^19",
    "react-dom": "^19"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^19",
    "typescript": "^5",
    "vitest": "^3",
    "prettier": "^3",
    "eslint": "^9",
    "eslint-config-next": "^15"
  }
}
```

## .gitignore
```
node_modules/
.next/
out/
.env
.env.local
*.tsbuildinfo
.worktrees/
.superflow/
# Explicit entries for event log artifacts (redundant with .superflow/ above, kept for self-documentation).
.superflow/events.jsonl
.superflow/archive/
.superflow-state.json
CLAUDE.local.md
```

## tsconfig.json
Standard Next.js tsconfig with strict mode enabled.

## README.md template
```markdown
# {project_name}

{project_description}

## Getting Started

npm install
npm run dev

Open http://localhost:3000.

## Development

- `npm run dev` — development server
- `npm run build` — production build
- `npm test` — run tests
- `npm run lint` — lint code
- `npm run format` — format code
```
