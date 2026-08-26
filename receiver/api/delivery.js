import { head } from "@vercel/blob";

function authorized(request) {
  return (
    process.env.RECEIVER_READ_TOKEN &&
    request.headers["x-receiver-read-token"] === process.env.RECEIVER_READ_TOKEN
  );
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
    const blob = await head(`deliveries/${guid}.json`, {
      token: process.env.BLOB_READ_WRITE_TOKEN,
    });
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
