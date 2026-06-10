import Wrapper from "./Wrapper";

// Enable dynamic routes in static export mode
export function generateStaticParams() {
  return [{ taskId: "dummy" }];
}

export default function Page() {
  return <Wrapper />;
}
