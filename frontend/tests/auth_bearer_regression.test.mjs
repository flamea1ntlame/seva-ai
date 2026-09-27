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

  await t.test("6. On 401 from /api/auth/me, clears stale seva_token and dispatches session_expired event", async () => {
    const staleToken = "expired_stale_token_abc";
    const storage = new Map([["seva_token", staleToken]]);

    let expiredDispatched = false;
    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
      dispatchEvent: (event) => {
        if (event?.type === "seva:session_expired") {
          expiredDispatched = true;
        }
        return true;
      },
    };

    globalThis.fetch = async (url) => {
      if (url.includes("/api/auth/me")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Could not validate credentials" }),
        };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    };

    let caughtError = null;
    try {
      await fetchApi("/api/auth/me");
    } catch (err) {
      caughtError = err;
    }

    assert.ok(caughtError, "Expected ApiError on 401 from /api/auth/me");
    assert.equal(caughtError.status, 401);
    assert.equal(storage.get("seva_token"), undefined, "Stale seva_token must be removed from localStorage on 401 from /api/auth/me");
    assert.equal(expiredDispatched, true, "seva:session_expired event must be dispatched on 401 from /api/auth/me");
  });

  await t.test("7. Complete fresh login flow: stores new access_token as seva_token and immediately validates with /api/auth/me", async () => {
    // 1. Initial state: stale token in storage
    const storage = new Map([["seva_token", "old_expired_token"]]);
    let currentUser = { id: "old-user" };
    let redirectedRoute = null;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    const mockRouter = {
      replace: (url) => { redirectedRoute = url; },
      push: (url) => { redirectedRoute = url; },
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
      dispatchEvent: (event) => {
        if (event?.type === "seva:session_expired") {
          currentUser = null;
          storage.delete("seva_token");
          mockRouter.replace("/login");
        }
        return true;
      },
    };

    const freshAccessToken = "fresh_jwt_access_token_999";
    const freshUserData = { id: "new-citizen-id-456", email: "citizen@example.com", full_name: "Citizen Test" };
    const meHeadersSent = [];

    globalThis.fetch = async (url, opts) => {
      if (url.includes("/api/auth/me")) {
        const authHeader = opts?.headers?.Authorization || opts?.headers?.authorization;
        meHeadersSent.push(authHeader);
        if (authHeader === `Bearer ${freshAccessToken}`) {
          return { ok: true, status: 200, json: async () => freshUserData };
        }
        return { ok: false, status: 401, json: async () => ({ detail: "Could not validate credentials" }) };
      }
      if (url.includes("/api/auth/login")) {
        return { ok: true, status: 200, json: async () => ({ access_token: freshAccessToken, token_type: "bearer" }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    };

    // 2. Initial validation with stale token fails with 401
    try {
      await fetchApi("/api/auth/me");
    } catch {}

    assert.equal(storage.get("seva_token"), undefined, "Stale token must be cleared");
    assert.equal(currentUser, null, "User state must be cleared");
    assert.equal(redirectedRoute, "/login", "Clean redirect to /login must occur");

    // 3. Citizen logs in: /api/auth/login returns fresh token
    const loginData = await fetchApi("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "citizen@example.com", password: "password123" }),
    });

    assert.equal(loginData.access_token, freshAccessToken);

    // 4. Store the NEW access_token as seva_token
    globalThis.localStorage.setItem("seva_token", loginData.access_token);
    assert.equal(globalThis.localStorage.getItem("seva_token"), freshAccessToken);

    // 5. Immediately validate the NEW token with /api/auth/me
    const verifiedUser = await fetchApi("/api/auth/me");
    currentUser = verifiedUser;
    mockRouter.replace("/dashboard");

    assert.equal(currentUser.id, "new-citizen-id-456");
    assert.equal(redirectedRoute, "/dashboard");
    assert.equal(meHeadersSent[meHeadersSent.length - 1], `Bearer ${freshAccessToken}`);
  });
});
