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

export async function GET(
  request: Request,
  { params }: { params: { taskId: string } }
) {
  const { taskId } = params;

  // FastAPI SSE endpoint is /api/tasks/{task_id}/progress (not /events)
  const sseUrl = `${API_BASE}/api/tasks/${taskId}/progress`;

  try {
    const userHeaders = getUserHeaders(request);

    const response = await fetch(sseUrl, {
      headers: {
        'Content-Type': 'application/json',
        ...userHeaders,
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to connect to SSE endpoint' },
        { status: response.status }
      );
    }

    // Create a streaming response that proxies the SSE stream
    const stream = new ReadableStream({
      async start(controller) {
        const reader = response.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              controller.close();
              break;
            }
            controller.enqueue(value);
          }
        } catch {
          controller.close();
        }
      },
    });

    return new NextResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
