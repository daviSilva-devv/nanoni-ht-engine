import {NextRequest, NextResponse} from "next/server";

const backend = process.env.NANONI_BACKEND_URL ?? "http://127.0.0.1:8010";
const token = process.env.NANONI_ADMIN_TOKEN ?? "change-me-local";
const responseHeaders = [
  "accept-ranges",
  "content-disposition",
  "content-length",
  "content-range",
  "content-type",
  "etag",
  "last-modified",
];

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function forward(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  try {
    const {path} = await context.params;
    const safePath = path.map(segment => encodeURIComponent(segment)).join("/");
    const target = new URL(`/api/v1/content/${safePath}`, backend);
    target.search = request.nextUrl.search;

    const headers = new Headers({"X-Admin-Token": token});
    for (const name of ["accept", "content-type", "range", "if-range"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    const hasBody = !["GET", "HEAD"].includes(request.method);
    const init: RequestInit & {duplex?: "half"} = {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      cache: "no-store",
      redirect: "manual",
    };
    if (hasBody) init.duplex = "half";

    const response = await fetch(target, init);
    const forwardedHeaders = new Headers();
    for (const name of responseHeaders) {
      const value = response.headers.get(name);
      if (value) forwardedHeaders.set(name, value);
    }
    return new NextResponse(response.body, {status: response.status, headers: forwardedHeaders});
  } catch {
    return NextResponse.json({detail: "Backend indisponível."}, {status: 502});
  }
}

export const GET = forward;
export const HEAD = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
