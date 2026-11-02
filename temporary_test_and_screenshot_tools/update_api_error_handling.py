path = "frontend/src/api.ts"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# Add friendly error helper function
helper_func = """
export function getFriendlyApiErrorMessage(status: number, detail?: string): string {
  if (detail && typeof detail === "string") {
    const trimmed = detail.trim();
    if (
      trimmed.length > 0 &&
      trimmed.length < 120 &&
      !trimmed.includes("Traceback") &&
      !trimmed.includes("OperationalError") &&
      !trimmed.includes("Exception") &&
      !trimmed.includes("<") &&
      !trimmed.includes("{")
    ) {
      return trimmed;
    }
  }

  switch (status) {
    case 400:
      return "The request was invalid. Please check your laboratory input data.";
    case 401:
      return "Your session has expired or requires authentication. Please sign in.";
    case 403:
      return "You do not have administrative permission for this action.";
    case 404:
      return "The requested laboratory record, sample, or experiment could not be found.";
    case 409:
      return "A record with this name or code already exists, or was updated in another session.";
    case 422:
      return "Invalid data formatting. Please check the values you entered.";
    case 429:
      return "Too many requests. Please wait a moment before trying again.";
    case 500:
    case 502:
    case 503:
    case 504:
      return "The laboratory service is temporarily unavailable. Please try again shortly.";
    default:
      return `Operation could not be completed (Status ${status}). Please try again.`;
  }
}
"""

assert "async function request<T>" in norm_text, "request function not found"

# Replace request() error handling
old_request = """  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }"""

new_request = """  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    const friendlyMsg = getFriendlyApiErrorMessage(response.status, body?.detail);
    const err = new Error(friendlyMsg);
    (err as any).status = response.status;
    throw err;
  }"""

assert old_request in norm_text, "old_request not found"
norm_text = norm_text.replace(old_request, new_request, 1)

# Also wrap fetch in request() with try/catch
old_fetch = """  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response = await fetch(path, { ...init, headers });"""

new_fetch = """  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new Error("Unable to connect to the laboratory server. Please check your network connection.");
  }"""

assert old_fetch in norm_text, "old_fetch not found"
norm_text = norm_text.replace(old_fetch, new_fetch, 1)

# Replace downloadBlob error handling
old_blob_err = """  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }"""

new_blob_err = """  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(getFriendlyApiErrorMessage(response.status, body?.detail));
  }"""

assert old_blob_err in norm_text, "old_blob_err not found"
norm_text = norm_text.replace(old_blob_err, new_blob_err, 1)

# Replace authRequest error handling
old_auth_req = """  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }"""

new_auth_req = """  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    const friendlyMsg = getFriendlyApiErrorMessage(response.status, body?.detail);
    const err = new Error(friendlyMsg);
    (err as any).status = response.status;
    throw err;
  }"""

assert old_auth_req in norm_text, "old_auth_req not found"
norm_text = norm_text.replace(old_auth_req, new_auth_req, 1)

# Also wrap authRequest fetch
old_auth_fetch = """async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });"""

new_auth_fetch = """async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error("Unable to connect to the authentication service. Please check your network connection.");
  }"""

assert old_auth_fetch in norm_text, "old_auth_fetch not found"
norm_text = norm_text.replace(old_auth_fetch, new_auth_fetch, 1)

# Insert helper function before request()
target_anchor = "async function request<T>"
norm_text = norm_text.replace(target_anchor, helper_func + "\n" + target_anchor, 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully updated api.ts with user-friendly error formatting!")
