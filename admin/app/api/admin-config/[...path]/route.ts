import {NextRequest, NextResponse} from "next/server";

const backend = process.env.NANONI_BACKEND_URL ?? "http://127.0.0.1:8010";
const token = process.env.NANONI_ADMIN_TOKEN ?? "change-me-local";

async function forward(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path} = await context.params;
  const target = new URL(`/api/v1/admin-config/${path.join("/")}`, backend);
  target.search = request.nextUrl.search;
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();
  const response = await fetch(target, {
    method: request.method,
    headers: {"Content-Type": "application/json", "X-Admin-Token": token},
    body: body || undefined,
    cache: "no-store",
  });
  return new NextResponse(response.status === 204 ? null : await response.text(), {
    status: response.status,
    headers: {"Content-Type": response.headers.get("Content-Type") ?? "application/json"},
  });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
