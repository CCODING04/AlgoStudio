import { NextResponse } from 'next/server';
import crypto from 'crypto';

const API_KEY = process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY || '';
const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const RBAC_SECRET_KEY = process.env.RBAC_SECRET_KEY || '';

// Generate auth headers for backend
function getAuthHeaders(request: Request): Record<string, string> {
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

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const authHeaders = getAuthHeaders(request);

    const res = await fetch(`${API_BASE}/api/deploy/worker`, {
      method: 'POST',
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
        ...authHeaders,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const error = await res.json();
      return NextResponse.json(
        { error: 'Failed to create deploy worker', details: error },
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
