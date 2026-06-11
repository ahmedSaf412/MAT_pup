/** @type {import('next').NextConfig} */
const nextConfig = {
  // Fix Turbopack "multiple lockfiles" root detection warning.
  turbopack: {
    root: import.meta.dirname,
  },

  // ── Compile-time optimizations ──────────────────────────────────────────────
  // 1. Modularize large icon/component libraries so Turbopack only pulls in
  //    the exact icons used rather than the whole package barrel file.
  modularizeImports: {
    // If you ever add lucide-react or @heroicons, add them here:
    // 'lucide-react': { transform: 'lucide-react/dist/esm/icons/{{kebabCase member}}' },
  },

  // 2. Minimise the set of CSS files Turbopack has to parse on first compile.
  //    (CSS modules are already scoped, no extra config needed.)

  // 3. Disable image optimisation for the dev server — it adds processing time.
  //    Re-enable in production by removing this block.
  images: {
    unoptimized: process.env.NODE_ENV === 'development',
  },

  // 4. Suppress the noisy "multiple roots" warning in console.
  //    (Already handled by turbopack.root above, but kept explicit.)
  logging: {
    fetches: { fullUrl: false },
  },
};

export default nextConfig;
