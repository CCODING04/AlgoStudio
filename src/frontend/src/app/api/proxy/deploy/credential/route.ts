import { NextResponse } from 'next/server';

// Store credentials in memory (in production, this would be stored securely server-side)
// For now, we generate a credential_id and the actual credential is stored client-side
const credentialStore = new Map<string, { username: string; created_at: string }>();

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { username, password } = body;

    if (!username || !password) {
      return NextResponse.json(
        { error: 'Username and password are required' },
        { status: 400 }
      );
    }

    // Generate a credential ID
    const credentialId = `cred_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    // Store metadata (not the password - in production, password would be hashed/stored securely)
    credentialStore.set(credentialId, {
      username,
      created_at: new Date().toISOString(),
    });

    return NextResponse.json({
      credential_id: credentialId,
      username,
      message: 'Credential stored successfully',
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to store credential' },
      { status: 500 }
    );
  }
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const credentialId = url.searchParams.get('credential_id');

  if (!credentialId) {
    return NextResponse.json(
      { error: 'credential_id is required' },
      { status: 400 }
    );
  }

  const credential = credentialStore.get(credentialId);

  if (!credential) {
    return NextResponse.json(
      { error: 'Credential not found' },
      { status: 404 }
    );
  }

  return NextResponse.json({
    credential_id: credentialId,
    username: credential.username,
    created_at: credential.created_at,
  });
}
