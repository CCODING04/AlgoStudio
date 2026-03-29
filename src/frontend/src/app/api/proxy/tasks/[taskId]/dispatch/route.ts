import { NextResponse } from 'next/server';
import crypto from 'crypto';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const RBAC_SECRET_KEY = process.env.RBAC_SECRET_KEY || '';

function getUserHeaders(request: Request): Record<string, string> {
  const userId = request.headers.get('X-User-ID') || 'test-user';
  const userRole = request.headers.get('X-User-Role') || 'admin';
  const timestamp = Math.floor(Date.now() / 1000).toString();

  let signature = '';
  if (RBAC_SECRET_KEY) {
    const message = `${userId}:${timestamp}`;
    signature = crypto
      .createHmac('sha256', RBAC_SECRET_KEY)
      .update(message)
      .digest('hex');
  }

  return {
    'X-User-ID': userId,
    'X-User-Role': userRole,
    'X-Timestamp': timestamp,
    'X-Signature': signature,
  };
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;

  try {
    const userHeaders = getUserHeaders(request);
    const body = await request.json().catch(() => ({}));

    const res = await fetch(`${API_BASE}/api/tasks/${taskId}/dispatch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...userHeaders,
      },
      body: JSON.stringify({ node_id: body.node_id || null }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      return NextResponse.json(
        { error: 'Failed to dispatch task', details: errorText },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
