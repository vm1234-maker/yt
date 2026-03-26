import { NextResponse } from "next/server";

/** Lightweight check for sandbox → host.docker.internal connectivity (no DB). */
export async function GET() {
  return NextResponse.json({ ok: true, service: "next" });
}
