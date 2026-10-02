// Type declarations for checking the Deno handler from the frontend test suite.
declare const Deno: {
  env: { get(name: string): string | undefined };
  serve(handler: (request: Request) => Promise<Response>): unknown;
};
declare module 'npm:@supabase/supabase-js@2' {
  export const createClient: typeof import('@supabase/supabase-js').createClient;
}
