import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  {
    // Server pages catch only awaited data fetches to render a typed ErrorState (network / 404 / 403 / 429 / 5xx);
    // the "JSX inside try" rule targets render-time errors in client components, which this is not.
    files: ["app/**/page.tsx"],
    rules: { "react-hooks/error-boundaries": "off" },
  },
  { ignores: [".next/**", "node_modules/**", "node_modules */**", "**/* 2/**", "lib/api-types.ts", "tests/e2e/**", "playwright-report/**", "test-results/**", "next-env.d.ts"] },
];

export default config;
