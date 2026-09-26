import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, getApiBaseUrl, fetchApi } from "../src/lib/api.ts";
import backendConfig from "../src/lib/backendConfig.js";
const { resolveBackendUrl } = backendConfig;

test("API Error Handling & Base URL Regression Suite", async (t) => {
  const originalEnv = process.env.NEXT_PUBLIC_API_URL;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
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

  await t.test("16. resolveBackendUrl throws explicit error in production when backend URL is missing", () => {
    assert.throws(
      () => resolveBackendUrl({ NODE_ENV: "production" }),
      (err) => {
        assert.match(err.message, /SEVA API CONFIG ERROR/i);
        assert.match(err.message, /Missing backend API URL in production/i);
        assert.match(err.message, /must not target localhost/i);
        return true;
      }
    );
  });

  await t.test("17. resolveBackendUrl throws explicit error in Vercel preview/production when backend URL is missing", () => {
    assert.throws(
      () => resolveBackendUrl({ VERCEL: "1", VERCEL_ENV: "preview" }),
      (err) => {
        assert.match(err.message, /SEVA API CONFIG ERROR/i);
        assert.match(err.message, /must not target localhost/i);
        return true;
      }
    );
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
});
