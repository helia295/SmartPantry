import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_BASE_URL =
  process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function buildBackendUrl(request: NextRequest, path: string[]) {
  const normalizedBase = BACKEND_BASE_URL.endsWith("/")
    ? BACKEND_BASE_URL.slice(0, -1)
    : BACKEND_BASE_URL;
  const target = new URL(
    `${normalizedBase}/${path.map((segment) => encodeURIComponent(segment)).join("/")}`
  );
  target.search = new URL(request.url).search;
  return target;
}

function buildForwardHeaders(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete("connection");
  headers.delete("content-length");
  headers.delete("host");
  headers.set("x-forwarded-host", request.headers.get("host") || "");
  headers.set("x-forwarded-proto", "https");
  return headers;
}

async function proxyRequest(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const targetUrl = buildBackendUrl(request, params.path || []);
  const headers = buildForwardHeaders(request);
  const method = request.method.toUpperCase();

  try {
    const backendResponse = await fetch(targetUrl, {
      method,
      headers,
      body: method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });

    const responseHeaders = new Headers(backendResponse.headers);
    responseHeaders.delete("content-length");

    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: "Backend proxy request failed.",
        backend_url: BACKEND_BASE_URL,
        error: error instanceof Error ? error.message : "Unknown proxy error",
      },
      { status: 502 }
    );
  }
}

export { proxyRequest as GET };
export { proxyRequest as POST };
export { proxyRequest as PUT };
export { proxyRequest as PATCH };
export { proxyRequest as DELETE };
export { proxyRequest as OPTIONS };
export { proxyRequest as HEAD };
