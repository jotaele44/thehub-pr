import { federation } from "@/api/federationClient";

export async function requireReviewerEmail() {
  const email = (await federation.auth.me())?.email;
  const reviewer = typeof email === "string" ? email.trim() : "";
  if (!reviewer) {
    throw new Error("Signed-in reviewer identity unavailable; verification was not recorded.");
  }
  return reviewer;
}
