import test from "node:test";
import assert from "node:assert/strict";
import { fetchApi, normalizeEndpoint } from "../src/lib/api.ts";

test("Authentication Regression: Authenticated requests send Authorization: Bearer <token>", async (t) => {
  const originalWindow = globalThis.window;
  const originalLocalStorage = globalThis.localStorage;
  const originalFetch = globalThis.fetch;

  t.afterEach(() => {
    globalThis.window = originalWindow;
    globalThis.localStorage = originalLocalStorage;
    globalThis.fetch = originalFetch;
  });

  await t.test("1. fetchApi adds Authorization: Bearer <token> from seva_token on /api/applications/", async () => {
    const fakeToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_payload.fake_signature";
    const storage = new Map([["seva_token", fakeToken]]);

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
    };

    let capturedUrl = null;
    let capturedHeaders = null;

    globalThis.fetch = async (url, opts) => {
      capturedUrl = url;
      capturedHeaders = opts?.headers;
      return {
        ok: true,
        status: 200,
        json: async () => [{ id: "app-123", status: "DRAFT" }],
      };
    };

    const res = await fetchApi("/api/applications/");

    assert.ok(capturedHeaders, "Headers must be passed to fetch");
    assert.equal(
      capturedHeaders["Authorization"],
      `Bearer ${fakeToken}`,
      "Must include Authorization: Bearer <token> header"
    );
    assert.equal(capturedUrl, "http://localhost:8000/api/applications/");
    assert.deepEqual(res, [{ id: "app-123", status: "DRAFT" }]);
  });

  await t.test("2. fetchApi adds Authorization: Bearer <token> on /api/documents/", async () => {
    const fakeToken = "doc_vault_valid_token_xyz";
    const storage = new Map([["seva_token", fakeToken]]);

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
    };

    let capturedHeaders = null;

    globalThis.fetch = async (url, opts) => {
      capturedHeaders = opts?.headers;
      return {
        ok: true,
        status: 200,
        json: async () => [{ id: "doc-1", title: "Aadhaar Card" }],
      };
    };

    await fetchApi("/api/documents/");

    assert.ok(capturedHeaders, "Headers must be passed to fetch");
    assert.equal(
      capturedHeaders["Authorization"],
      `Bearer ${fakeToken}`,
      "Must include Authorization: Bearer <token> header on /api/documents/"
    );
  });

  await t.test("3. normalizeEndpoint ensures collection endpoints end with trailing slash to prevent 307/308 redirects", () => {
    assert.equal(normalizeEndpoint("/api/applications"), "/api/applications/");
    assert.equal(normalizeEndpoint("/api/applications/"), "/api/applications/");
    assert.equal(normalizeEndpoint("/api/documents"), "/api/documents/");
    assert.equal(normalizeEndpoint("/api/documents/"), "/api/documents/");
    assert.equal(normalizeEndpoint("/api/services"), "/api/services/");
    assert.equal(normalizeEndpoint("/api/audit"), "/api/audit/");
    assert.equal(normalizeEndpoint("/api/auth/me"), "/api/auth/me");
    assert.equal(normalizeEndpoint("/api/documents/vault-stats"), "/api/documents/vault-stats");
  });

  await t.test("4. fetchApi normalizes incoming headers and overrides stale or lowercase authorization", async () => {
    const validToken = "fresh_verified_token";
    const storage = new Map([["seva_token", validToken]]);

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
    };

    let capturedHeaders = null;

    globalThis.fetch = async (url, opts) => {
      capturedHeaders = opts?.headers;
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      };
    };

    // Caller passes stale authorization header in options
    await fetchApi("/api/applications/", {
      headers: { authorization: "Bearer stale_bad_token" },
    });

    assert.equal(
      capturedHeaders["Authorization"],
      `Bearer ${validToken}`,
      "Fresh token from localStorage must override any stale/lowercase authorization"
    );
    assert.equal(
      capturedHeaders["authorization"],
      undefined,
      "Duplicate lowercase authorization header must be removed"
    );
  });

  await t.test("5. fetchApi does not include Authorization header when seva_token is null", async () => {
    globalThis.localStorage = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
    };

    let capturedHeaders = null;

    globalThis.fetch = async (url, opts) => {
      capturedHeaders = opts?.headers;
      return {
        ok: true,
        status: 200,
        json: async () => [],
      };
    };

    await fetchApi("/api/services/");
    assert.equal(capturedHeaders["Authorization"], undefined);
  });
});
