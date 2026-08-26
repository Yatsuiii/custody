import crypto from "node:crypto";
import { head, put } from "@vercel/blob";
import { bodyDigest, parseVerifiedPayload } from "../lib/verify.js";
const MAX_BODY_BYTES = 2 * 1024 * 1024;

export const config = {
  api: {
    bodyParser: false,
    maxDuration: 10,
    sizeLimit: "2mb",
  },
};

function header(request, name) {
  const value = request.headers[name.toLowerCase()];
  return Array.isArray(value) ? value[0] : value;
}

function jsonError(response, status, code) {
  response.status(status).json({ ok: false, code });
}

async function readRawBody(request) {
  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += bytes.length;
    if (total > MAX_BODY_BYTES) {
      throw new Error("body_too_large");
    }
    chunks.push(bytes);
  }
  return Buffer.concat(chunks);
}

function isAlreadyExists(error) {
  return (
    error?.status === 409 ||
    error?.statusCode === 409 ||
    /already exists|already uploaded|precondition/i.test(String(error?.message || ""))
  );
}

async function ensureUnique(pathname, envelope) {
  try {
    await head(pathname, { token: process.env.BLOB_READ_WRITE_TOKEN });
    return "duplicate";
  } catch (error) {
    if (error?.status && error.status !== 404 && error?.statusCode !== 404) {
      throw error;
    }
  }
  try {
    await put(pathname, envelope, {
      access: "private",
      addRandomSuffix: false,
      allowOverwrite: false,
      contentType: "application/json",
      cacheControlMaxAge: 60,
      token: process.env.BLOB_READ_WRITE_TOKEN,
    });
    return "stored";
  } catch (error) {
    if (isAlreadyExists(error)) {
      return "duplicate";
    }
    throw error;
  }
}

export default async function webhook(request, response) {
  if (request.method !== "POST") {
    response.setHeader("allow", "POST");
    return jsonError(response, 405, "method_not_allowed");
  }
  if (!process.env.WEBHOOK_SECRET || !process.env.BLOB_READ_WRITE_TOKEN) {
    return jsonError(response, 503, "receiver_not_configured");
  }
  const delivery = header(request, "x-github-delivery");
  const event = header(request, "x-github-event");
  const signature = header(request, "x-hub-signature-256");
  if (!delivery || !/^[0-9a-f-]{20,80}$/i.test(delivery)) {
    return jsonError(response, 400, "missing_delivery_guid");
  }
  let rawBody;
  try {
    rawBody = await readRawBody(request);
  } catch (error) {
    return jsonError(response, 413, error?.message === "body_too_large" ? "body_too_large" : "body_read_failed");
  }
  const verified = parseVerifiedPayload({
    rawBody,
    signature,
    secret: process.env.WEBHOOK_SECRET,
    event,
  });
  if (!verified.accepted) {
    return jsonError(response, verified.status, verified.code);
  }
  const receivedAt = new Date().toISOString();
  const envelope = JSON.stringify({
    schema: "github-issue-comment-raw-delivery-v1",
    delivery_guid: delivery,
    received_at: receivedAt,
    headers: {
      "x-github-delivery": delivery,
      "x-github-event": event,
      "x-hub-signature-256": signature,
    },
    body_sha256: bodyDigest(rawBody),
    body_b64: rawBody.toString("base64"),
  });
  try {
    const outcome = await ensureUnique(`deliveries/${delivery}.json`, envelope);
    response.status(200).json({ ok: true, delivery, outcome });
  } catch (error) {
    console.error("durable_delivery_write_failed", {
      delivery,
      name: error?.name,
      status: error?.status || error?.statusCode,
    });
    return jsonError(response, 503, "durable_write_failed");
  }
}
