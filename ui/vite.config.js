import { defineConfig } from "vite";
import { viteStaticCopy } from 'vite-plugin-static-copy';
import { svelte } from '@sveltejs/vite-plugin-svelte'

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";


function resolveInputs(directory) {
    const inputs = fs
        .readdirSync(directory, { withFileTypes: true, })
        .reduce((acc, entry) => {
            if (entry.isFile()) {
                const file = entry.name;
                const filename = path.parse(file).name;
                const filepath = path.join(directory, file);

                acc[filename] = fileURLToPath(new URL(filepath, import.meta.url));
            } else {
                const subDirectory = entry.name;
                const filepath = path.join(directory, subDirectory, 'index.js');

                if (fs.existsSync(filepath)) {
                    acc[subDirectory] = fileURLToPath(new URL(filepath, import.meta.url));
                }
            }

            return acc;
        }, {});

    return inputs;
}

export default defineConfig(({ mode }) => {
    const production = (mode === 'production');
    const development = (mode === 'development');


    return {
        build: {
            minify: false,
            manifest: false,
            outDir: 'dist',
            rollupOptions: {
                input: resolveInputs('./src/pages'),
                output: {
                    manualChunks: undefined,
                    entryFileNames: 'assets/js/iris/[name].js',
                    chunkFileNames: 'assets/js/chunks/[name]-[hash].js',
                    assetFileNames: 'assets/[ext]/[name].[ext]',
                },
                treeshake: false,
            },
            sourcemap: (development) ? 'inline': false,
        },
        resolve: {
            alias: {
                '$lib': path.resolve('./src/lib'),
            },
        },
        plugins: [
            svelte({
                emitCss: false,
                inspector: development,
            }),
            viteStaticCopy({
                targets: [
                    // Core
                    {
                        src: 'node_modules/bootstrap/dist/js/bootstrap.min.js',
                        dest: 'assets/js/core',
                    },
                    {
                        src: 'node_modules/jquery/dist/jquery.min.js',
                        dest: 'assets/js/core',
                        rename: 'jquery.3.2.1.min.js',
                    },
                    {
                        src: 'node_modules/jquery-validation/dist/jquery.validate.min.js',
                        dest: 'assets/js/core',
                        rename: 'jquery.validate.js',
                    },
                    {
                        src: 'node_modules/moment/min/moment.min.js',
                        dest: 'assets/js/core',
                        rename: 'moments.min.js',
                    },
                    {
                        src: 'node_modules/popper.js/dist/umd/popper.min.js',
                        dest: 'assets/js/core',
                    },
                    {
                        src: 'node_modules/socket.io/client-dist/socket.io.min.js',
                        dest: 'assets/js/core',
                        rename: 'socket.io.js',
                    },
                    {
                        src: 'node_modules/chart.js/dist/Chart.min.js',
                        dest: 'assets/js/core',
                        rename: 'charts.js',
                    },
                    // Plugins
                    {
                        src: 'node_modules/ace-builds/src-noconflict/',
                        dest: 'assets/js/plugin/ace/',
                    },
                    {
                        src: 'node_modules/bootstrap-slider/dist/bootstrap-slider.min.js',
                        dest: 'assets/js/plugin/bootstrap-slider/',
                    },
                    {
                        src: 'node_modules/dropzone/dist/min/dropzone.min.js',
                        dest: 'assets/js/plugin/dropzone/',
                    },
                    {
                        src: 'node_modules/html2canvas/dist/html2canvas.min.js',
                        dest: 'assets/js/plugin/html2canvas/',
                    },
                    {
                        src: 'node_modules/jquery.scrollbar/jquery.scrollbar.min.js',
                        dest: 'assets/js/plugin/jquery-scrollbar/',
                    },
                    {
                        src: 'node_modules/jquery-ui-touch-punch/jquery.ui.touch-punch.min.js',
                        dest: 'assets/js/plugin/jquery-ui-touch-punch/',
                    },
                    {
                        src: 'node_modules/jqvmap/dist/jquery.vmap.min.js',
                        dest: 'assets/js/plugin/jqvmap/',
                    },
                    {
                        src: 'node_modules/jqvmap/dist/maps',
                        dest: 'assets/js/plugin/jqvmap/',
                    },
                    {
                        src: 'node_modules/showdown/dist/showdown.min.js',
                        dest: 'assets/js/plugin/showdown/',
                    },
                    {
                        src: 'node_modules/sortablejs/Sortable.min.js',
                        dest: 'assets/js/plugin/sortable/',
                        rename: 'sortable.js',
                    },
                    {
                        src: 'node_modules/vis/dist/vis.min.js',
                        dest: 'assets/js/plugin/vis/',
                    },
                    {
                        src: 'node_modules/vis/dist/vis-network.min.js',
                        dest: 'assets/js/plugin/vis/',
                    },
                    {
                        src: 'node_modules/vis/dist/vis-timeline-graph2d.min.js',
                        dest: 'assets/js/plugin/vis/',
                        rename: 'vis.graph.js'
                    },
                    {
                        src: 'node_modules/webfontloader/webfontloader.js',
                        dest: 'assets/js/plugin/webfont/',
                        rename: 'webfont.min.js'
                    },
                    {
                        src: 'node_modules/xss/dist/xss.min.js',
                        dest: 'assets/js/plugin/xss/',
                        rename: 'xss.js',
                    },
                ]
            }),
        ],
    }
});
