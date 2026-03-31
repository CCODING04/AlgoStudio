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

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get('status');
  const node_ip = searchParams.get('node_ip');
  const authHeaders = getAuthHeaders(request);

  let url = `${API_BASE}/api/deploy/workers`;
  const queryParams = [];
  if (status) queryParams.push(`status=${status}`);
  if (node_ip) queryParams.push(`node_ip=${node_ip}`);
  if (queryParams.length > 0) url += `?${queryParams.join('&')}`;

  try {
    const res = await fetch(url, {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
        ...authHeaders,
      },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch deploy workers' },
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
