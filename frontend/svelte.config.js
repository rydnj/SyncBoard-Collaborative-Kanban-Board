import adapter from '@sveltejs/adapter-node';
// adapter-node builds SvelteKit for a standalone Node.js server (outputs to /build)
// adapter-auto (the default) tries to detect the deployment platform — doesn't work for Docker

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter()
  }
};

export default config;