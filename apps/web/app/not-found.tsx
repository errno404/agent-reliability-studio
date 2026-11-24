import Link from "next/link";
import { Card, EmptyState } from "@/components/ui";

export default function NotFound() {
  return <Card><EmptyState title="Page not found" action={<Link className="text-accent underline" href="/">Back to overview</Link>}>That page or resource does not exist.</EmptyState></Card>;
}
