import { get, head } from "@vercel/blob";

const MAX_ENVELOPE_BYTES = 4 * 1024 * 1024;

function authorized(request) {
  return (
    process.env.RECEIVER_READ_TOKEN &&
    request.headers["x-receiver-read-token"] === process.env.RECEIVER_READ_TOKEN
  );
}

async function readEnvelope(pathname) {
  const result = await get(pathname, {
    access: "private",
    token: process.env.BLOB_READ_WRITE_TOKEN,
  });
  if (!result) {
    return null;
  }
  const chunks = [];
  let total = 0;
  for await (const chunk of result.stream) {
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += bytes.length;
    if (total > MAX_ENVELOPE_BYTES) {
      throw new Error("envelope_too_large");
    }
    chunks.push(bytes);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export default async function delivery(request, response) {
  if (request.method !== "GET") {
    response.setHeader("allow", "GET");
    return response.status(405).json({ ok: false, code: "method_not_allowed" });
  }
  if (!authorized(request)) {
    return response.status(404).json({ ok: false, code: "not_found" });
  }
  const guid = String(request.query?.guid || "");
  if (!/^[0-9a-f-]{20,80}$/i.test(guid)) {
    return response.status(400).json({ ok: false, code: "invalid_delivery_guid" });
  }
  try {
    const pathname = `deliveries/${guid}.json`;
    const blob = await head(pathname, {
      token: process.env.BLOB_READ_WRITE_TOKEN,
    });
    if (request.query?.content === "1") {
      const envelope = await readEnvelope(pathname);
      if (!envelope || envelope.schema !== "github-issue-comment-raw-delivery-v1") {
        return response.status(502).json({ ok: false, code: "invalid_delivery_envelope" });
      }
      return response.status(200).json(envelope);
    }
    return response.status(200).json({
      pathname: blob.pathname,
      url: blob.url,
      download_url: blob.downloadUrl,
      etag: blob.etag,
    });
  } catch (error) {
    const status = error?.status || error?.statusCode;
    return response.status(status === 404 ? 404 : 503).json({
      ok: false,
      code: status === 404 ? "not_found" : "blob_read_failed",
    });
  }
}
