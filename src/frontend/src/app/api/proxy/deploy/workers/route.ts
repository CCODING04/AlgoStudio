import { NextResponse } from 'next/server';

const API_KEY = process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY || '';
const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get('status');
  const node_ip = searchParams.get('node_ip');

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
