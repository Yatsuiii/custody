export default function health(_request, response) {
  const configured = Boolean(
    process.env.WEBHOOK_SECRET &&
      process.env.BLOB_READ_WRITE_TOKEN &&
      process.env.RECEIVER_READ_TOKEN,
  );
  response.status(200).json({
    service: "custody-external-validity-signed-ingress",
    status: configured ? "ready" : "misconfigured",
    schema: "github-issue-comment-raw-delivery-v1",
  });
}
