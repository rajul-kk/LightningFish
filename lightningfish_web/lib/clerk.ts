/**
 * Clerk is optional in this app: with a real publishable key the full auth UI
 * renders, without one (or with the committed placeholder) the public pages
 * still work and auth-gated pages degrade to a notice.
 *
 * The flag lives here rather than in layout.tsx because every page that calls
 * a Clerk hook has to agree with the layout about whether a <ClerkProvider>
 * exists. When it didn't, `next build` failed at prerender with "useUser can
 * only be used within the <ClerkProvider /> component" — a deploy blocker that
 * only appears when Clerk is unconfigured, i.e. exactly on a fresh clone.
 *
 * NEXT_PUBLIC_ so it is readable from client components too.
 */
const CLERK_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

/** The placeholder shipped in .env.local.example — present but not usable. */
const PLACEHOLDER_KEY = "pk_test_bGlnaHRuaW5nZmlzaC5sb2NhbGhvc3Qk";

export const HAS_CLERK = CLERK_KEY.startsWith("pk_") && CLERK_KEY !== PLACEHOLDER_KEY;
