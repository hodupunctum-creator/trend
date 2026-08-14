/**
 * 이메일의 "리포트 생성 시작" 버튼(링크) 클릭을 받아서
 * GitHub Actions의 repository_dispatch 이벤트를 발생시키는 경량 서버리스 함수.
 *
 * 필요한 Worker Secrets (wrangler secret put 으로 등록):
 *   TRIGGER_SECRET   - generate_trigger_token.py와 동일한 공유 비밀키 (토큰 서명 검증용)
 *   GITHUB_TOKEN      - repository_dispatch 호출 권한을 가진 GitHub PAT (repo scope)
 *   GITHUB_OWNER      - 예: "your-org"
 *   GITHUB_REPO       - 예: "sns-trend-report"
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/trigger") {
      return new Response("Not Found", { status: 404 });
    }

    const token = url.searchParams.get("token");
    if (!token) {
      return htmlResponse("토큰이 없습니다.", 400);
    }

    const valid = await verifyToken(token, env.TRIGGER_SECRET);
    if (!valid.ok) {
      return htmlResponse(`유효하지 않은 요청입니다: ${valid.reason}`, 403);
    }

    // GitHub repository_dispatch 호출
    const ghResp = await fetch(
      `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "User-Agent": "sns-trend-report-worker",
        },
        body: JSON.stringify({ event_type: "run-pipeline" }),
      }
    );

    if (ghResp.status !== 204) {
      const body = await ghResp.text();
      return htmlResponse(`GitHub 트리거 실패 (status ${ghResp.status}): ${body}`, 502);
    }

    return htmlResponse(
      "✅ 리포트 생성이 시작되었습니다. 완료되면 별도 메일로 발송됩니다 (수 분 소요).",
      200
    );
  },
};

async function verifyToken(token, secret) {
  const parts = token.split(".");
  if (parts.length !== 2) return { ok: false, reason: "malformed token" };
  const [payloadB64, sigB64] = parts;

  const expectedSig = await hmacSha256Base64Url(payloadB64, secret);
  if (expectedSig !== sigB64) return { ok: false, reason: "invalid signature" };

  let payload;
  try {
    payload = JSON.parse(base64UrlDecode(payloadB64));
  } catch {
    return { ok: false, reason: "invalid payload" };
  }

  if (!payload.exp || Date.now() / 1000 > payload.exp) {
    return { ok: false, reason: "token expired" };
  }

  return { ok: true };
}

async function hmacSha256Base64Url(message, secret) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sigBuf = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return base64UrlEncode(new Uint8Array(sigBuf));
}

function base64UrlEncode(bytes) {
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/");
  while (str.length % 4) str += "=";
  return atob(str);
}

function htmlResponse(message, status) {
  return new Response(
    `<!DOCTYPE html><html lang="ko"><body style="font-family:sans-serif;text-align:center;padding:60px;">
      <h2>${message}</h2>
    </body></html>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}
