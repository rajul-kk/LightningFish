import { NextRequest, NextResponse } from "next/server";

const PY = process.env.PYTHON_SERVICE_URL ?? "http://localhost:8000";
const SERVICE_SECRET = process.env.SERVICE_SECRET ?? "";

export async function POST(req: NextRequest) {
  const body = await req.json();

  const res = await fetch(`${PY}/simulate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(SERVICE_SECRET ? { "X-Service-Secret": SERVICE_SECRET } : {}),
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
