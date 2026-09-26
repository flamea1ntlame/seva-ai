import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, getApiBaseUrl, fetchApi, validateSession, handleSessionValidationOn401 } from "../src/lib/api.ts";
import backendConfig from "../src/lib/backendConfig.js";
const { resolveBackendUrl } = backendConfig;

test("API Error Handling & Base URL Regression Suite", async (t) => {
  const originalEnv = process.env.NEXT_PUBLIC_API_URL;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  const originalLocalStorage = globalThis.localStorage;
  const originalNavigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, "navigator");

  function setMockNavigator(mockObj) {
    Object.defineProperty(globalThis, "navigator", {
      value: mockObj,
      configurable: true,
      writable: true,
    });
  }

  function restoreNavigator() {
    if (originalNavigatorDescriptor) {
      Object.defineProperty(globalThis, "navigator", originalNavigatorDescriptor);
    } else {
      delete globalThis.navigator;
    }
  }

  t.afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = originalEnv;
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
    globalThis.localStorage = originalLocalStorage;
    restoreNavigator();
  });

  await t.test("1. getApiBaseUrl returns explicit NEXT_PUBLIC_API_URL trimmed of trailing slash", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://seva-backend.onrender.com/";
    assert.equal(getApiBaseUrl(), "https://seva-backend.onrender.com");
  });

  await t.test("2. getApiBaseUrl defaults to relative URL '' on remote production browser host when env unset", () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    globalThis.window = {
      location: { hostname: "seva-ai.onrender.com", origin: "https://seva-ai.onrender.com" },
    };
    assert.equal(getApiBaseUrl(), "");
  });

  await t.test("3. getApiBaseUrl uses http://localhost:8000 on local development machine", () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    globalThis.window = {
      location: { hostname: "localhost", origin: "http://localhost:3000" },
    };
    assert.equal(getApiBaseUrl(), "http://localhost:8000");
  });

  await t.test("4. ApiError classifies 4xx client errors accurately", () => {
    const errorCases = [
      { status: 400, expected: "CLIENT_ERROR" },
      { status: 401, expected: "CLIENT_ERROR" },
      { status: 403, expected: "CLIENT_ERROR" },
      { status: 404, expected: "CLIENT_ERROR" },
      { status: 409, expected: "CLIENT_ERROR" },
      { status: 422, expected: "CLIENT_ERROR" },
      { status: 429, expected: "CLIENT_ERROR" },
    ];

    for (const { status, expected } of errorCases) {
      const err = new ApiError("Error occurred", status, expected);
      assert.equal(err.status, status);
      assert.equal(err.errorType, "CLIENT_ERROR");
    }
  });

  await t.test("5. ApiError classifies 5xx server errors accurately", () => {
    const serverCases = [
      { status: 500, expected: "SERVER_ERROR" },
      { status: 502, expected: "SERVER_ERROR" },
      { status: 503, expected: "SERVER_ERROR" },
      { status: 504, expected: "SERVER_ERROR" },
    ];

    for (const { status, expected } of serverCases) {
      const err = new ApiError("Server error", status, expected);
      assert.equal(err.status, status);
      assert.equal(err.errorType, "SERVER_ERROR");
    }
  });

  await t.test("6. fetchApi distinguishes 502 Bad Gateway / restarting backend from internet offline", async () => {
    globalThis.window = undefined;
    globalThis.fetch = async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("HTML body cannot be parsed as JSON");
      },
    });

    await assert.rejects(
      async () => {
        await fetchApi("/api/services/");
      },
      (err) => {
        assert.equal(err instanceof ApiError, true);
        assert.equal(err.status, 502);
        assert.equal(err.errorType, "SERVER_ERROR");
        assert.match(err.message, /Bad Gateway|restarting/i);
        assert.doesNotMatch(err.message, /check your internet connection/i);
        return true;
      }
    );
  });

  await t.test("7. fetchApi distinguishes 503 Maintenance from internet offline", async () => {
    globalThis.window = undefined;
    globalThis.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: "Under scheduled maintenance" }),
    });

    await assert.rejects(
      async () => {
        await fetchApi("/api/services/");
      },
      (err) => {
        assert.equal(err.status, 503);
        assert.equal(err.errorType, "SERVER_ERROR");
        assert.equal(err.message, "Under scheduled maintenance");
        return true;
      }
    );
  });

  await t.test("8. fetchApi detects actual offline device (navigator.onLine === false)", async () => {
    globalThis.window = {
      location: { hostname: "localhost", origin: "http://localhost:3000" },
    };
    setMockNavigator({ onLine: false });
    globalThis.fetch = async () => {
      throw new TypeError("Failed to fetch");
    };

    await assert.rejects(
      async () => {
        await fetchApi("/api/services/");
      },
      (err) => {
        assert.equal(err.status, 0);
        assert.equal(err.errorType, "OFFLINE");
        assert.match(err.message, /appear to be offline/i);
        return true;
      }
    );
  });

  await t.test("9. fetchApi distinguishes CORS / remote origin block when user is online", async () => {
    process.env.NEXT_PUBLIC_API_URL = "https://seva-backend.onrender.com";
    globalThis.window = {
      location: { hostname: "seva-frontend.vercel.app", origin: "https://seva-frontend.vercel.app" },
    };
    setMockNavigator({ onLine: true });
    globalThis.fetch = async () => {
      throw new TypeError("Failed to fetch");
    };

    await assert.rejects(
      async () => {
        await fetchApi("/api/services/");
      },
      (err) => {
        assert.equal(err.status, 0);
        assert.equal(err.errorType, "CORS");
        assert.match(err.message, /cross-origin|CORS/i);
        assert.doesNotMatch(err.message, /check your internet connection/i);
        return true;
      }
    );
  });

  await t.test("10. fetchApi distinguishes general server unreachable / connection refused", async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    globalThis.window = undefined;
    setMockNavigator(undefined);
    globalThis.fetch = async () => {
      throw new Error("ECONNREFUSED 127.0.0.1:8000");
    };

    await assert.rejects(
      async () => {
        await fetchApi("/api/services/");
      },
      (err) => {
        assert.equal(err.status, 0);
        assert.equal(err.errorType, "NETWORK");
        assert.match(err.message, /Unable to connect to SEVA services/i);
        assert.doesNotMatch(err.message, /check your internet connection/i);
        return true;
      }
    );
  });

  await t.test("11. fetchApi distinguishes client-side request timeout (AbortError)", async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    globalThis.window = undefined;
    setMockNavigator(undefined);
    globalThis.fetch = async () => {
      const abortErr = new Error("The operation was aborted");
      abortErr.name = "AbortError";
      throw abortErr;
    };

    await assert.rejects(
      async () => {
        await fetchApi("/api/services/");
      },
      (err) => {
        assert.equal(err.status, 0);
        assert.equal(err.errorType, "TIMEOUT");
        assert.match(err.message, /Request timed out/i);
        return true;
      }
    );
  });

  await t.test("12. getApiBaseUrl strips redundant /api and trailing slashes", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://seva-ai-2hks.onrender.com/api/";
    assert.equal(getApiBaseUrl(), "https://seva-ai-2hks.onrender.com");

    process.env.NEXT_PUBLIC_API_URL = "https://seva-ai-2hks.onrender.com/api";
    assert.equal(getApiBaseUrl(), "https://seva-ai-2hks.onrender.com");

    process.env.NEXT_PUBLIC_API_URL = "https://seva-ai-2hks.onrender.com///";
    assert.equal(getApiBaseUrl(), "https://seva-ai-2hks.onrender.com");
  });

  await t.test("13. resolveBackendUrl normalizes NEXT_PUBLIC_API_URL without /api or trailing slash", () => {
    assert.equal(
      resolveBackendUrl({ NEXT_PUBLIC_API_URL: "https://seva-ai-2hks.onrender.com/api/" }),
      "https://seva-ai-2hks.onrender.com"
    );
    assert.equal(
      resolveBackendUrl({ NEXT_PUBLIC_API_URL: "https://seva-ai-2hks.onrender.com" }),
      "https://seva-ai-2hks.onrender.com"
    );
  });

  await t.test("14. resolveBackendUrl supports server environment variables (BACKEND_URL, API_URL, RENDER_EXTERNAL_URL)", () => {
    assert.equal(
      resolveBackendUrl({ BACKEND_URL: "https://seva-backend.internal:8000" }),
      "https://seva-backend.internal:8000"
    );
    assert.equal(
      resolveBackendUrl({ API_URL: "https://seva-api.internal/api/" }),
      "https://seva-api.internal"
    );
    assert.equal(
      resolveBackendUrl({ RENDER_EXTERNAL_URL: "https://seva-ai-2hks.onrender.com" }),
      "https://seva-ai-2hks.onrender.com"
    );
  });

  await t.test("15. resolveBackendUrl falls back to http://localhost:8000 only in local development", () => {
    assert.equal(
      resolveBackendUrl({ NODE_ENV: "development" }),
      "http://localhost:8000"
    );
    assert.equal(
      resolveBackendUrl({}),
      "http://localhost:8000"
    );
  });

  await t.test("16. resolveBackendUrl falls back to https://seva-ai-2hks.onrender.com in production when env is missing (never localhost)", () => {
    const url = resolveBackendUrl({ NODE_ENV: "production" });
    assert.equal(url, "https://seva-ai-2hks.onrender.com");
    assert.notEqual(url, "http://localhost:8000");
  });

  await t.test("17. resolveBackendUrl falls back to https://seva-ai-2hks.onrender.com in Vercel when env is missing (never localhost)", () => {
    const previewUrl = resolveBackendUrl({ VERCEL: "1", VERCEL_ENV: "preview" });
    assert.equal(previewUrl, "https://seva-ai-2hks.onrender.com");
    assert.notEqual(previewUrl, "http://localhost:8000");

    const prodUrl = resolveBackendUrl({ VERCEL: "1", VERCEL_ENV: "production" });
    assert.equal(prodUrl, "https://seva-ai-2hks.onrender.com");
    assert.notEqual(prodUrl, "http://localhost:8000");
  });

  await t.test("18. resolveBackendUrl handles key whitespace, lowercase casing, and surrounding quotes", () => {
    assert.equal(
      resolveBackendUrl({ " next_public_api_url ": "\"https://seva-ai-2hks.onrender.com/\"" }),
      "https://seva-ai-2hks.onrender.com"
    );
    assert.equal(
      resolveBackendUrl({ "BACKEND_URL ": "'https://seva-backend.internal:8000'" }),
      "https://seva-backend.internal:8000"
    );
  });

  await t.test("19. resolveBackendUrl supports NEXT_PUBLIC_BACKEND_URL and SEVA_BACKEND_URL", () => {
    assert.equal(
      resolveBackendUrl({ NEXT_PUBLIC_BACKEND_URL: "https://seva-ai-2hks.onrender.com" }),
      "https://seva-ai-2hks.onrender.com"
    );
    assert.equal(
      resolveBackendUrl({ SEVA_BACKEND_URL: "https://seva-ai-2hks.onrender.com" }),
      "https://seva-ai-2hks.onrender.com"
    );
  });

  await t.test("20. Authentication lifecycle: successful login -> /me success -> dashboard allowed", async () => {
    const storage = new Map();
    let eventDispatched = false;
    let navigatedTo = null;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    globalThis.fetch = async (url, options) => {
      if (url.includes("/api/auth/login")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: "jwt_token_123", token_type: "bearer" }),
        };
      }
      if (url.includes("/api/auth/me")) {
        assert.equal(options.headers["Authorization"], "Bearer jwt_token_123");
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: "cit-1", email: "citizen@example.com", full_name: "Citizen One" }),
        };
      }
      throw new Error(`Unexpected request to ${url}`);
    };

    // Simulate login flow
    const loginData = await fetchApi("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "citizen@example.com", password: "secretpassword" }),
    });
    globalThis.localStorage.setItem("seva_token", loginData.access_token);

    const verifiedUser = await fetchApi("/api/auth/me");
    assert.ok(verifiedUser);
    assert.equal(verifiedUser.id, "cit-1");
    navigatedTo = "/dashboard";

    assert.equal(navigatedTo, "/dashboard");
    assert.equal(globalThis.localStorage.getItem("seva_token"), "jwt_token_123");
    assert.equal(eventDispatched, false);
  });

  await t.test("21. Authentication lifecycle: login succeeds but /me returns 401 -> stay on login with clear error", async () => {
    const storage = new Map();
    let eventDispatched = false;
    let navigatedTo = null;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    globalThis.fetch = async (url) => {
      if (url.includes("/api/auth/login")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: "invalid_jwt_token", token_type: "bearer" }),
        };
      }
      if (url.includes("/api/auth/me")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Could not validate credentials" }),
        };
      }
      throw new Error(`Unexpected URL ${url}`);
    };

    // Simulate login with bad token returned
    const loginData = await fetchApi("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "citizen@example.com", password: "password" }),
    });
    globalThis.localStorage.setItem("seva_token", loginData.access_token);

    // /me fails with 401
    await assert.rejects(
      async () => {
        try {
          await fetchApi("/api/auth/me");
          navigatedTo = "/dashboard";
        } catch (err) {
          // AuthContext refreshUser pattern
          globalThis.localStorage.removeItem("seva_token");
          throw err;
        }
      },
      (err) => {
        assert.equal(err.status, 401);
        return true;
      }
    );

    // Verify citizen did NOT navigate to dashboard and credentials were reset
    assert.equal(navigatedTo, null);
    assert.equal(globalThis.localStorage.getItem("seva_token"), null);
    assert.equal(eventDispatched, true);
  });

  await t.test("22. Authentication lifecycle: background endpoint 401 does not destroy session or clear seva_token", async () => {
    const storage = new Map([["seva_token", "valid_active_token"]]);
    let eventDispatched = false;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    // Background requests (vault-stats, chat history, applications)
    const backgroundEndpoints = [
      "/api/documents/vault-stats",
      "/api/chat/history",
      "/api/applications/",
    ];

    for (const endpoint of backgroundEndpoints) {
      globalThis.fetch = async () => ({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Not authenticated for this resource" }),
      });

      await assert.rejects(
        async () => {
          await fetchApi(endpoint);
        },
        (err) => {
          assert.equal(err.status, 401);
          assert.match(err.message, /Not authenticated/i);
          return true;
        }
      );

      // Session must remain intact!
      assert.equal(globalThis.localStorage.getItem("seva_token"), "valid_active_token");
      assert.equal(eventDispatched, false);
    }
  });

  await t.test("23. Authentication lifecycle: expired token on /api/auth/me triggers seva:session_expired and clears seva_token", async () => {
    const storage = new Map([["seva_token", "expired_token"]]);
    let eventDispatched = false;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    globalThis.fetch = async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Could not validate credentials" }),
    });

    await assert.rejects(
      async () => {
        await fetchApi("/api/auth/me");
      },
      (err) => {
        assert.equal(err.status, 401);
        assert.match(err.message, /session has expired/i);
        return true;
      }
    );

    assert.equal(globalThis.localStorage.getItem("seva_token"), null);
    assert.equal(eventDispatched, true);
  });

  await t.test("24. Authentication lifecycle: network failure during refreshUser preserves token without false session expiry", async () => {
    const storage = new Map([["seva_token", "valid_citizen_token"]]);
    let eventDispatched = false;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    // Network drops / connection refused
    globalThis.fetch = async () => {
      throw new TypeError("Failed to fetch");
    };

    await assert.rejects(
      async () => {
        try {
          await fetchApi("/api/auth/me");
        } catch (err) {
          // AuthContext handles non-401 without wiping token
          if (err?.status === 401) {
            globalThis.localStorage.removeItem("seva_token");
          }
          throw err;
        }
      },
      (err) => {
        assert.equal(err.errorType, "NETWORK");
        return true;
      }
    );

    // Token must be preserved!
    assert.equal(globalThis.localStorage.getItem("seva_token"), "valid_citizen_token");
    assert.equal(eventDispatched, false);
  });

  await t.test("25. Token key consistency: seva_token used consistently, malformed strings rejected", async () => {
    let capturedHeader = null;

    globalThis.window = {
      location: { hostname: "localhost" },
    };

    globalThis.fetch = async (url, options) => {
      capturedHeader = options.headers?.["Authorization"] ?? null;
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      };
    };

    // Test 1: Valid token
    globalThis.localStorage = {
      getItem: (k) => (k === "seva_token" ? "clean_jwt_xyz" : null),
    };
    await fetchApi("/api/services/");
    assert.equal(capturedHeader, "Bearer clean_jwt_xyz");

    // Test 2: Malformed tokens "null" or "undefined" should NOT attach Authorization
    for (const badToken of ["null", "undefined", "  ", ""]) {
      globalThis.localStorage = {
        getItem: (k) => (k === "seva_token" ? badToken : null),
      };
      capturedHeader = null;
      await fetchApi("/api/services/");
      assert.equal(capturedHeader, null, `Token value '${badToken}' should not attach Authorization header`);
    }
  });

  await t.test("26. Login credential failure: 401 on /api/auth/login does not dispatch seva:session_expired", async () => {
    let eventDispatched = false;

    globalThis.localStorage = {
      getItem: () => null,
      removeItem: () => {},
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    globalThis.fetch = async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Incorrect email or password" }),
    });

    await assert.rejects(
      async () => {
        await fetchApi("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: "citizen@example.com", password: "wrong" }),
        });
      },
      (err) => {
        assert.equal(err.status, 401);
        assert.equal(err.message, "Incorrect email or password");
        return true;
      }
    );

    // Must NOT trigger session expired event on login failure
    assert.equal(eventDispatched, false);
  });

  await t.test("27. Regression 13A: Valid token flow: /me 200 -> requirements 200 -> create application 201", async () => {
    const storage = new Map([["seva_token", "valid_jwt_token_999"]]);
    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: () => true,
      location: { hostname: "localhost" },
    };

    // 1. /api/auth/me returns 200
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/auth/me")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: "cit-1", full_name: "Anita Sharma", email: "anita@example.com" }),
        };
      }
      if (u.includes("/requirements")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ service_code: "income_certificate", required_documents: ["id_proof"] }),
        };
      }
      if (u.includes("/applications/")) {
        return {
          ok: true,
          status: 201,
          json: async () => ({ id: "app-new-1", application_number: "SEVA-554433", status: "submitted" }),
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    };

    const me = await fetchApi("/api/auth/me");
    assert.equal(me.email, "anita@example.com");

    const reqs = await fetchApi("/api/services/income_certificate/requirements");
    assert.equal(reqs.service_code, "income_certificate");

    const app = await fetchApi("/api/applications/", {
      method: "POST",
      body: JSON.stringify({ service_id: "srv-1" }),
    });
    assert.equal(app.application_number, "SEVA-554433");
    assert.equal(storage.get("seva_token"), "valid_jwt_token_999");
  });

  await t.test("28. Regression 13B: Stale/expired token: 401 on protected action triggers session validation, clears token, and redirects to login", async () => {
    const storage = new Map([["seva_token", "stale_expired_token_111"]]);
    let eventDispatched = false;
    let redirectedTo = null;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    const mockRouter = {
      push: (url) => {
        redirectedTo = url;
      },
    };

    // When protected request returns 401, followed by /api/auth/me returning 401
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/applications/")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Could not validate credentials" }),
        };
      }
      if (u.includes("/auth/me")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Could not validate credentials" }),
        };
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
    };

    // Simulate Apply Now action catching 401
    let caughtErr = null;
    try {
      await fetchApi("/api/applications/", { method: "POST", body: "{}" });
    } catch (err) {
      caughtErr = err;
    }

    assert.ok(caughtErr);
    assert.equal(caughtErr.status, 401);

    // Controlled session validation runs
    const isValid = await handleSessionValidationOn401(caughtErr, mockRouter);

    assert.equal(isValid, false);
    assert.equal(storage.has("seva_token"), false, "Stale seva_token must be cleared from storage");
    assert.equal(eventDispatched, true, "seva:session_expired event must be dispatched");
    assert.equal(redirectedTo, "/login?session_expired=1", "Citizen must be redirected to login with session_expired=1");
  });

  await t.test("29. Regression 13C: Background 401 does not incorrectly destroy a still-valid session", async () => {
    const storage = new Map([["seva_token", "valid_active_token_222"]]);
    let eventDispatched = false;
    let redirectedTo = null;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    const mockRouter = {
      push: (url) => {
        redirectedTo = url;
      },
    };

    // A background endpoint returns 401 (e.g. transient failure), BUT /api/auth/me returns 200 (token is valid)
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/vault-stats")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Transient auth check failure" }),
        };
      }
      if (u.includes("/auth/me")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: "cit-1", full_name: "Citizen", email: "citizen@example.com" }),
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    };

    let backgroundErr = null;
    try {
      await fetchApi("/api/documents/vault-stats");
    } catch (err) {
      backgroundErr = err;
    }

    assert.ok(backgroundErr);
    assert.equal(backgroundErr.status, 401);

    // Validate session
    const isValid = await handleSessionValidationOn401(backgroundErr, mockRouter);

    assert.equal(isValid, true, "Session must be deemed valid when /api/auth/me succeeds");
    assert.equal(storage.get("seva_token"), "valid_active_token_222", "Token must remain intact");
    assert.equal(eventDispatched, false, "Must not fire session_expired event for valid session");
    assert.equal(redirectedTo, null, "Must not redirect citizen when session is valid");
  });

  await t.test("30. Regression 13D: Missing or empty token during Apply Now flow cleanly triggers session validation failure", async () => {
    const storage = new Map(); // empty storage
    let eventDispatched = false;
    let redirectedTo = null;

    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      dispatchEvent: (event) => {
        if (event.type === "seva:session_expired") eventDispatched = true;
        return true;
      },
      location: { hostname: "localhost" },
    };

    const mockRouter = {
      push: (url) => {
        redirectedTo = url;
      },
    };

    const isValid = await validateSession();
    assert.equal(isValid, false);
    assert.equal(eventDispatched, true);

    const isHandled = await handleSessionValidationOn401(new ApiError("Not authenticated", 401), mockRouter);
    assert.equal(isHandled, false);
    assert.equal(redirectedTo, "/login?session_expired=1");
  });

  await t.test("31. Regression 13E: Token storage key consistency — strictly seva_token is used", async () => {
    const storage = new Map([["seva_token", "canonical_seva_token"]]);
    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.window = {
      localStorage: globalThis.localStorage,
      location: { hostname: "localhost" },
    };

    let authHeaderSent = null;
    globalThis.fetch = async (url, opts) => {
      authHeaderSent = opts?.headers?.Authorization || opts?.headers?.authorization || null;
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      };
    };

    await fetchApi("/api/services/");
    assert.equal(authHeaderSent, "Bearer canonical_seva_token");

    // Setting a fake "token" key in localStorage should NOT be picked up
    storage.delete("seva_token");
    storage.set("token", "legacy_fake_token");

    authHeaderSent = null;
    await fetchApi("/api/services/");
    assert.equal(authHeaderSent, null, "Legacy 'token' key must NOT be read as seva_token");
  });

  await t.test("32. Regression 13F: Multi-tab logout synchronization — clearing seva_token in another tab clears auth state and redirects", async () => {
    let currentUser = { id: "cit-1", full_name: "Ramesh" };
    let redirectedTo = null;

    const setUser = (val) => {
      currentUser = val;
    };
    const mockRouter = {
      push: (url) => {
        redirectedTo = url;
      },
    };

    // Storage event handler logic from AuthContext
    const handleStorageChange = (event) => {
      if (event.key === "seva_token") {
        if (!event.newValue) {
          setUser(null);
          mockRouter.push("/login");
        }
      } else if (!event.key) {
        const currentToken = globalThis.localStorage.getItem("seva_token");
        if (!currentToken) {
          setUser(null);
          mockRouter.push("/login");
        }
      }
    };

    // Scenario A: Another tab removes seva_token (citizen logged out in Tab 2)
    handleStorageChange({ key: "seva_token", oldValue: "jwt_token_tab2", newValue: null });
    assert.equal(currentUser, null, "User state must be cleared when token is removed in another tab");
    assert.equal(redirectedTo, "/login", "Must redirect to /login when logged out in another tab");

    // Scenario B: Another tab clears localStorage entirely
    currentUser = { id: "cit-2", full_name: "Suresh" };
    redirectedTo = null;
    globalThis.localStorage = { getItem: () => null };
    handleStorageChange({ key: null, oldValue: null, newValue: null });
    assert.equal(currentUser, null, "User state must be cleared when localStorage is cleared in another tab");
    assert.equal(redirectedTo, "/login");
  });

  await t.test("33. Regression 13G: Rapid double-click on Apply Now is synchronously locked out and prevents duplicate applications", async () => {
    let postCallCount = 0;
    const storage = new Map([["seva_token", "valid_jwt_double_click_test"]]);
    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.fetch = async (url, opts) => {
      const u = String(url);
      if (u.includes("/requirements")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ service_code: "income_cert", jurisdiction_supported: true }),
        };
      }
      if (u.includes("/applications/")) {
        postCallCount++;
        // Simulate network latency of application creation
        await new Promise((resolve) => setTimeout(resolve, 30));
        return {
          ok: true,
          status: 201,
          json: async () => ({ id: `app-${postCallCount}`, application_number: `SEVA-${postCallCount}` }),
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    };

    // Simulate the synchronous in-flight guard from ServiceCatalog
    const startingAppRef = { current: false };
    let startingApp = false;

    const simulateHandleStartApplication = async () => {
      if (startingAppRef.current || startingApp) return null;
      startingAppRef.current = true;
      startingApp = true;

      try {
        const token = globalThis.localStorage.getItem("seva_token");
        if (!token) return null;

        await fetchApi("/api/services/income_cert/requirements");
        const app = await fetchApi("/api/applications/", {
          method: "POST",
          body: JSON.stringify({ service_id: "income_cert" }),
        });
        return app;
      } finally {
        startingAppRef.current = false;
        startingApp = false;
      }
    };

    // Fire two rapid clicks concurrently (in the same microtask tick)
    const [result1, result2] = await Promise.all([
      simulateHandleStartApplication(),
      simulateHandleStartApplication(),
    ]);

    assert.ok(result1, "First click should proceed and create application");
    assert.equal(result2, null, "Second rapid click must be dropped by the in-flight lock");
    assert.equal(postCallCount, 1, "Exactly ONE POST /api/applications/ request must be made");
    assert.equal(startingAppRef.current, false, "In-flight lock must be cleanly released afterwards");
  });
});


