import { NextResponse } from 'next/server';
import { headers } from 'next/headers';

const API_KEY = process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY || '';
const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const url = `${API_BASE}/api/hosts`;
    const requestHeaders = headers();

    const res = await fetch(url, {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
        // Forward user authentication headers from the browser request
        'X-User-ID': requestHeaders.get('X-User-ID') || 'test-user',
        'X-User-Role': requestHeaders.get('X-User-Role') || 'admin',
      },
      // Follow redirects manually to ensure proper response handling
      redirect: 'follow',
    });

    // After redirect, read the final response
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json(
        { error: 'Invalid JSON from backend', detail: text.substring(0, 200) },
        { status: 502 }
      );
    }

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch hosts', ...data },
        { status: res.status }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Hosts proxy error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
