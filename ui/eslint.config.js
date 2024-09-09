import globals from "globals";
import pluginJs from "@eslint/js";

import eslintPluginSvelte from 'eslint-plugin-svelte';

import svelteConfig from './svelte.config.js';


export default [
    {
        languageOptions: {
            globals: {
                ...globals.browser,
                ...globals.jquery,
            },
            parserOptions: {
                svelteConfig,
            },
        },
    },
    pluginJs.configs.recommended,
    ...eslintPluginSvelte.configs["flat/recommended"],
    {
        rules: {
          // override/add rules settings here, such as:
          // 'svelte/rule-name': 'error'
        }
    }
];