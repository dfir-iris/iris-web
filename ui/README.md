# UI

## Getting Started

### Requirements

- [Node.js](https://nodejs.org/)

### Quick overview of tools

- [Vite](https://vitejs.dev/)
- [Eslint](https://eslint.org/)
- [Svelte](https://svelte.dev/)

## Development

First, we need to install dependencies:
```bash
npm install
```

Then, we can build IRIS application and rebuild it on changes:
```bash
npm run watch
```

To execute linting of source files:
```bash
npm run lint
```


## Production

First, we need to install dependencies:
```bash
npm ci
```

Then, we can build IRIS application:
```bash
npm run build
```

## Misc

Find outdated packages:
```bash
npm outdated
```

Find vulnerables packages:
```bash
npm audit
```

## Project Structure

Here are some of the most important directories under `ui` folder:
- `src`: IRIS specific JS files.
- `public`: Static assets such as images, fonts but also CSS and JS files from vendors (external libraries).
- `dist`: The dist folder, short for distribution folder, is dynamically generated when running one of the build commands listed above. The generation is a two steps process: first, `public` folder is copied into `dist` then JS code is bundled from `src` and copied into `dist`.
